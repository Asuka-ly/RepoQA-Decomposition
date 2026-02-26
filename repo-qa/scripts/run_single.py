"""单问题运行脚本 - 适配新架构与 SWE-QA question/repo 绑定。"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import argparse
from pathlib import Path

import litellm
import yaml

# 禁用 SSL 验证（应对代理问题）
litellm.ssl_verify = False

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.utils import PATH_CONFIG
from src.agents import StrategicRepoQAAgent
from src.config import ExperimentConfig

from minisweagent.models import get_model
from minisweagent.models.test_models import DeterministicModel
from minisweagent.environments.local import LocalEnvironment
from minisweagent import package_dir


def _configure_network(keep_proxy: bool):
    if not keep_proxy:
        for key in [
            "http_proxy", "https_proxy", "all_proxy",
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE",
        ]:
            os.environ.pop(key, None)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run single RepoQA experiment")
    parser.add_argument("--keep-proxy", action="store_true", help="Do not clear proxy env vars")
    parser.add_argument("--config", default="baseline", help="Config name in repo-qa/configs")
    parser.add_argument(
        "--question-file",
        default="swe_qa_bench/swe_qa_0001.txt",
        help="Question filename in data/questions (supports subdir, e.g. swe_qa_bench/swe_qa_0001.txt)",
    )
    parser.add_argument("--repo-path", default=None, help="Override target repository path")
    parser.add_argument("--offline", action="store_true", help="Use deterministic offline model")
    parser.add_argument("--repo-cache-dir", default=None, help="Local cache dir for benchmark repositories")
    return parser.parse_args()


def _offline_outputs(repo_path: str):
    decomp_json = (
        '{"sub_questions":[{"id":"SQ1","sub_question":"How does DefaultAgent parse and execute actions?",'
        '"hypothesis":"parse_action validates bash action before execute",'
        '"entry_candidates":["agents/default.py::DefaultAgent.parse_action"],'
        '"symbols":["DefaultAgent","parse_action"],'
        '"required_evidence":["definition location","call path"],'
        '"exit_criterion":"2 grounded evidence items","status":"open","priority":1}],'
        '"synthesis":"Combine parser and run loop","estimated_hops":2,"unresolved_symbols":[]}'
    )
    return [
        decomp_json,
        f'Find DefaultAgent\n```bash\ncd {repo_path} && rg "class DefaultAgent" agents/default.py\n```',
        f'Find parse_action line\n```bash\ncd {repo_path} && rg -n "def parse_action" agents/default.py\n```',
        f"Read parse_action with lines\n```bash\ncd {repo_path} && nl -ba agents/default.py | sed -n '120,180p'\n```",
        f"Read run loop with lines\n```bash\ncd {repo_path} && nl -ba agents/default.py | sed -n '180,250p'\n```",
        (
            "## FINAL ANSWER\n"
            "`DefaultAgent.parse_action` is defined in `agents/default.py` and its line location is confirmed via `rg -n`; "
            "the execution/observation handling is in `agents/default.py:131`, and parsing is in `agents/default.py:116`."
            "\n```bash\necho COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n```"
        ),
    ]


def _resolve_question_file(question_arg: str) -> Path:
    root = PATH_CONFIG.repo_qa_root / "data" / "questions"
    candidate = Path(question_arg)
    if candidate.is_absolute() and candidate.exists():
        return candidate

    direct = root / question_arg
    if direct.exists():
        return direct

    by_name = list(root.rglob(candidate.name))
    if len(by_name) == 1:
        return by_name[0]

    raise FileNotFoundError(f"Task file not found for arg '{question_arg}'")


def _load_question_metadata(task_file: Path) -> dict:
    index_path = task_file.parent / "index.jsonl"
    if not index_path.exists():
        return {}

    rel_to_parent = task_file.name
    rel_to_questions = str(task_file.relative_to(PATH_CONFIG.repo_qa_root / "data" / "questions"))

    with index_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            qf = row.get("question_file", "")
            if qf in {rel_to_parent, rel_to_questions}:
                return row
    return {}


def _repo_slug_to_url(repo_slug: str) -> str:
    slug = (repo_slug or "").strip()
    if slug.startswith(("http://", "https://", "git@")):
        return slug
    return f"https://github.com/{slug}.git"


def _repo_slug_to_local_dir(repo_slug: str) -> str:
    slug = (repo_slug or "unknown_repo").strip().replace("/", "__")
    return slug


def _run_checked(cmd: list[str], cwd: Path | None = None):
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def _ensure_repo_checkout(repo_slug: str, commit: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = cache_dir / _repo_slug_to_local_dir(repo_slug)

    if not repo_dir.exists():
        _run_checked(["git", "clone", _repo_slug_to_url(repo_slug), str(repo_dir)])

    _run_checked(["git", "fetch", "--all", "--tags"], cwd=repo_dir)

    if commit:
        try:
            _run_checked(["git", "checkout", commit], cwd=repo_dir)
        except subprocess.CalledProcessError:
            _run_checked(["git", "fetch", "origin", commit], cwd=repo_dir)
            _run_checked(["git", "checkout", commit], cwd=repo_dir)

    return repo_dir


def _resolve_target_repo(args: argparse.Namespace, task_file: Path, metadata: dict) -> tuple[str, dict]:
    if args.repo_path:
        return args.repo_path, {"mode": "manual", "repo": None, "commit": None}

    repo_slug = metadata.get("repo")
    commit = metadata.get("commit")
    if repo_slug:
        cache_dir = Path(args.repo_cache_dir) if args.repo_cache_dir else (PATH_CONFIG.project_root / "data" / "external" / "repo_cache")
        repo_dir = _ensure_repo_checkout(repo_slug, commit, cache_dir)
        return str(repo_dir), {"mode": "question_bound", "repo": repo_slug, "commit": commit}

    return PATH_CONFIG.get_test_repo_path(), {"mode": "default", "repo": None, "commit": None}


def main():
    args = parse_args()
    _configure_network(keep_proxy=args.keep_proxy)

    print("\n" + "=" * 60)
    print("🔍 Validating environment...")
    print("=" * 60 + "\n")

    if not PATH_CONFIG.validate():
        print("\n❌ Path validation failed!")
        return

    if not args.offline:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "your-api-key-here":
            print("❌ Error: Please set OPENAI_API_KEY in .env file")
            return
        print(f"✓ API Key loaded (length: {len(api_key)})")
    else:
        print("✓ Offline mode enabled: deterministic model")

    config_path = PATH_CONFIG.repo_qa_root / "configs" / f"{args.config}.yaml"
    print(f"\n📋 Loading config from: {config_path}")
    if not config_path.exists():
        print(f"❌ Error: Config file not found: {config_path}")
        return
    exp_config = ExperimentConfig.from_yaml(str(config_path))
    print(f"✓ Config loaded: {exp_config.name}")

    task_file = _resolve_question_file(args.question_file)
    task = task_file.read_text(encoding="utf-8")
    q_meta = _load_question_metadata(task_file)
    repo_path, repo_meta = _resolve_target_repo(args, task_file, q_meta)

    print("\n🤖 Initializing model and environment...")
    model_name = getattr(exp_config, "model_name", "gpt-4o")
    if not model_name.startswith(("openai/", "anthropic/", "azure/")):
        model_name = f"openai/{model_name}"

    print(f"🤖 Initializing model: {model_name}")
    api_base = os.getenv("OPENAI_API_BASE")
    if api_base:
        print(f"   Using API Base: {api_base}")
        os.environ["OPENAI_API_BASE"] = api_base

    if args.offline:
        model = DeterministicModel(outputs=_offline_outputs(repo_path))
    else:
        model = get_model(input_model_name=model_name)
    env = LocalEnvironment()

    agent_config_path = Path(package_dir) / "config" / "default.yaml"
    agent_config = yaml.safe_load(agent_config_path.read_text())

    print("🎯 Creating RepoQA Agent...")
    agent = StrategicRepoQAAgent(model, env, exp_config, **agent_config["agent"])

    print(f"\n{'=' * 60}")
    print(f"📝 Running task from: {task_file.name}")
    print(f"📦 Question binding mode: {repo_meta['mode']}")
    if repo_meta.get("repo"):
        print(f"🔗 Bound repo: {repo_meta['repo']}")
    if repo_meta.get("commit"):
        print(f"🧷 Bound commit: {repo_meta['commit']}")
    print(f"🎯 Target repo: {repo_path}")
    print(f"{'=' * 60}\n")

    try:
        result = agent.run(task, repo_path)
        status = result[0] if isinstance(result, (list, tuple)) else "Completed"
        print(f"\n✓ Final Status: {status}")
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
