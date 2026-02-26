"""离线冒烟实验：不依赖外部 API，验证 Stage1 管线与轨迹产物。"""

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.utils import PATH_CONFIG
from src.config import ExperimentConfig
from src.agents import StrategicRepoQAAgent, VanillaRepoQAAgent

from minisweagent.models.test_models import DeterministicModel
from minisweagent.environments.local import LocalEnvironment
from minisweagent import package_dir


def _agent_cfg():
    agent_config_path = Path(package_dir) / "config" / "default.yaml"
    return yaml.safe_load(agent_config_path.read_text())["agent"]


def _strategic_outputs(repo_path: str):
    decomp_json = {
        "sub_questions": [
            {
                "id": "SQ1",
                "sub_question": "How does DefaultAgent parse and execute actions?",
                "hypothesis": "Action parsing happens before command execution",
                "entry_candidates": ["agents/default.py::DefaultAgent.parse_action"],
                "symbols": ["DefaultAgent", "parse_action", "execute_action"],
                "required_evidence": ["definition location", "call path"],
                "exit_criterion": "2 grounded evidence items",
                "status": "open",
                "priority": 1,
            }
        ],
        "synthesis": "Combine parse logic and run loop",
        "estimated_hops": 2,
        "unresolved_symbols": [],
    }
    return [
        json.dumps(decomp_json),
        f"Read class anchor\n```bash\ncd {repo_path} && rg -n 'class DefaultAgent' agents/default.py\n```",
        f"Read parse_action symbol\n```bash\ncd {repo_path} && rg -n 'def parse_action' agents/default.py\n```",
        f"Read execute_action symbol\n```bash\ncd {repo_path} && rg -n 'def execute_action' agents/default.py\n```",
        f"Read call path context\n```bash\ncd {repo_path} && nl -ba agents/default.py | sed -n '110,280p'\n```",
        (
            "## FINAL ANSWER\n"
            "`DefaultAgent.parse_action` is defined at `agents/default.py:116`, validates a single bash code block near "
            "`agents/default.py:138`, and the action execution path is implemented in `agents/default.py:246`."
            "\n```bash\necho COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n```"
        ),
    ]


def _vanilla_outputs(repo_path: str):
    return [
        f"Explore files\n```bash\ncd {repo_path} && ls\n```",
        f"Inspect parse_action symbol\n```bash\ncd {repo_path} && rg -n 'def parse_action' agents/default.py\n```",
        f"Inspect execute path\n```bash\ncd {repo_path} && rg -n 'def execute_action' agents/default.py\n```",
        f"Inspect default agent body\n```bash\ncd {repo_path} && nl -ba agents/default.py | sed -n '120,260p'\n```",
        (
            "## FINAL ANSWER\n"
            "Action parsing constraints appear in `agents/default.py:116` and `agents/default.py:138`, with execution flow in "
            "`agents/default.py:246`."
            "\n```bash\necho COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n```"
        ),
    ]


def run_once(agent_cls, config_name: str, outputs: list[str], task: str, repo_path: str):
    cfg_path = PATH_CONFIG.repo_qa_root / "configs" / f"{config_name}.yaml"
    exp_cfg = ExperimentConfig.from_yaml(str(cfg_path))
    model = DeterministicModel(outputs=outputs)
    env = LocalEnvironment()
    agent = agent_cls(model=model, env=env, config=exp_cfg, **_agent_cfg())
    result = agent.run(task, repo_path)
    stats = agent._get_stats()
    return result, stats


def main():
    repo_path = PATH_CONFIG.get_test_repo_path()
    task = "How does DefaultAgent parse and execute actions?"

    print("=" * 60)
    print("OFFLINE SMOKE: strategic")
    print("=" * 60)
    _, s_stats = run_once(StrategicRepoQAAgent, "baseline", _strategic_outputs(repo_path), task, repo_path)
    print(s_stats)

    print("=" * 60)
    print("OFFLINE SMOKE: vanilla")
    print("=" * 60)
    _, v_stats = run_once(VanillaRepoQAAgent, "vanilla", _vanilla_outputs(repo_path), task, repo_path)
    print(v_stats)


if __name__ == "__main__":
    main()
