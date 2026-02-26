"""批量运行脚本：支持 Stage1 与 SWE-QA 问题集。"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List


DEFAULT_STAGE1_QUESTION_FILES = [
    "q1_timeout_exception.txt",
    "q2_config_loading.txt",
    "q3_default_agent_action_flow.txt",
    "q4_message_history_flow.txt",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RepoQA experiments in batch")
    parser.add_argument("--mode", choices=["single", "ablation", "both"], default="ablation")
    parser.add_argument("--question-files", default="", help="Comma separated question files")
    parser.add_argument("--all-questions", action="store_true", help="Run all questions of selected source")
    parser.add_argument(
        "--question-source",
        choices=["swe_qa", "stage1", "auto"],
        default="swe_qa",
        help="Question source. auto: prefer swe_qa if available, otherwise stage1.",
    )
    parser.add_argument("--config", default="baseline", help="Config used by run_single.py")
    parser.add_argument("--repo-path", default=None, help="Override target repository path")
    parser.add_argument("--offline", action="store_true", help="Use deterministic offline model")
    parser.add_argument("--keep-proxy", action="store_true", help="Do not clear proxy env vars")
    return parser.parse_args()


def _resolve_source(question_source: str, questions_dir: Path) -> str:
    if question_source in {"swe_qa", "stage1"}:
        return question_source
    index = questions_dir / "swe_qa_bench" / "index.jsonl"
    return "swe_qa" if index.exists() else "stage1"


def _normalize_question_file(questions_dir: Path, question_file: str) -> str | None:
    qf = (question_file or "").strip()
    if not qf:
        return None

    qf_path = Path(qf)
    if qf_path.is_absolute():
        return str(qf_path) if qf_path.exists() else None

    # 兼容 index 里写成 "swe_qa_0001.txt" 的情况
    if (questions_dir / qf_path).exists():
        return qf_path.as_posix()
    if (questions_dir / "swe_qa_bench" / qf_path.name).exists():
        return f"swe_qa_bench/{qf_path.name}"
    return None


def _all_swe_qa_files(questions_dir: Path) -> List[str]:
    index = questions_dir / "swe_qa_bench" / "index.jsonl"
    if not index.exists():
        return []

    files: List[str] = []
    seen: set[str] = set()
    for line in index.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        normalized = _normalize_question_file(questions_dir, row.get("question_file", ""))
        if normalized and normalized not in seen:
            files.append(normalized)
            seen.add(normalized)
    return files


def resolve_question_files(question_files_arg: str, all_questions: bool, source: str = "stage1", questions_dir: Path | None = None) -> List[str]:
    if question_files_arg.strip():
        items = [x.strip() for x in question_files_arg.split(",") if x.strip()]
        if items:
            return items

    if source == "swe_qa":
        if questions_dir is None:
            return []
        files = _all_swe_qa_files(questions_dir)
        if all_questions:
            return files
        return files[: min(10, len(files))]

    return list(DEFAULT_STAGE1_QUESTION_FILES)


def _build_command(script_name: str, args: argparse.Namespace, question_file: str) -> List[str]:
    cmd = [sys.executable, f"scripts/{script_name}", "--question-file", question_file]
    if script_name == "run_single.py":
        cmd.extend(["--config", args.config])
    if args.repo_path:
        cmd.extend(["--repo-path", args.repo_path])
    if args.offline:
        cmd.append("--offline")
    if args.keep_proxy:
        cmd.append("--keep-proxy")
    return cmd


def _run_one(script_name: str, args: argparse.Namespace, question_file: str) -> dict:
    cmd = _build_command(script_name, args, question_file)
    started = datetime.now()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    duration = (datetime.now() - started).total_seconds()
    return {
        "script": script_name,
        "question_file": question_file,
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "duration": round(duration, 2),
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-20:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-20:]),
        "status": "ok" if proc.returncode == 0 else "failed",
    }


def _question_exists(questions_dir: Path, qf: str) -> bool:
    candidate = Path(qf)
    if candidate.is_absolute():
        return candidate.exists()
    return (questions_dir / qf).exists()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    questions_dir = repo_root / "data" / "questions"

    source = _resolve_source(args.question_source, questions_dir)
    question_files = resolve_question_files(args.question_files, args.all_questions, source=source, questions_dir=questions_dir)
    if not question_files:
        print(f"❌ No questions resolved for source={source}. Please run fetch script first.")
        return 2

    missing = [q for q in question_files if not _question_exists(questions_dir, q)]
    if missing:
        print(f"❌ Missing question files: {missing}")
        return 2

    scripts = []
    if args.mode in {"single", "both"}:
        scripts.append("run_single.py")
    if args.mode in {"ablation", "both"}:
        scripts.append("run_ablation.py")

    print("=" * 72)
    print(f"🚀 Batch run start | mode={args.mode} | source={source} | questions={len(question_files)}")
    print("=" * 72)

    results = []
    for qf in question_files:
        print(f"\n🧩 Question: {qf}")
        for script in scripts:
            print(f"  ▶ Running {script} ...")
            one = _run_one(script, args, qf)
            results.append(one)
            marker = "✅" if one["returncode"] == 0 else "❌"
            print(f"  {marker} {script} ({one['duration']}s)")

    output_dir = repo_root / "experiments" / "comparison_reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = output_dir / f"batch_run_{ts}.json"

    summary = {
        "timestamp": ts,
        "mode": args.mode,
        "question_source": source,
        "questions": question_files,
        "offline": args.offline,
        "results": results,
        "total": len(results),
        "passed": sum(1 for r in results if r["returncode"] == 0),
        "failed": sum(1 for r in results if r["returncode"] != 0),
    }
    out_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 72)
    print("📊 Batch summary")
    print("=" * 72)
    print(f"- total jobs:  {summary['total']}")
    print(f"- passed:      {summary['passed']}")
    print(f"- failed:      {summary['failed']}")
    print(f"- report file: {out_file}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
