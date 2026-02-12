"""批量运行脚本：支持一次性跑完多题（默认 q1~q4）。"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List


DEFAULT_QUESTION_FILES = [
    "q1_timeout_exception.txt",
    "q2_config_loading.txt",
    "q3_default_agent_action_flow.txt",
    "q4_message_history_flow.txt",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RepoQA experiments in batch")
    parser.add_argument(
        "--mode",
        choices=["single", "ablation", "both"],
        default="ablation",
        help="Run run_single.py, run_ablation.py or both for each question",
    )
    parser.add_argument(
        "--question-files",
        default="",
        help="Comma separated question files in data/questions (e.g. q1.txt,q2.txt)",
    )
    parser.add_argument(
        "--all-questions",
        action="store_true",
        help="Run all built-in Stage1 questions (q1~q4)",
    )
    parser.add_argument("--config", default="baseline", help="Config used by run_single.py")
    parser.add_argument("--repo-path", default=None, help="Override target repository path")
    parser.add_argument("--offline", action="store_true", help="Use deterministic offline model")
    parser.add_argument("--keep-proxy", action="store_true", help="Do not clear proxy env vars")
    return parser.parse_args()


def resolve_question_files(question_files_arg: str, all_questions: bool) -> List[str]:
    if all_questions:
        return list(DEFAULT_QUESTION_FILES)

    if question_files_arg.strip():
        items = [x.strip() for x in question_files_arg.split(",") if x.strip()]
        if items:
            return items

    return list(DEFAULT_QUESTION_FILES)


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


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    question_files = resolve_question_files(args.question_files, args.all_questions)

    questions_dir = repo_root / "data" / "questions"
    missing = [q for q in question_files if not (questions_dir / q).exists()]
    if missing:
        print(f"❌ Missing question files: {missing}")
        return 2

    scripts = []
    if args.mode in {"single", "both"}:
        scripts.append("run_single.py")
    if args.mode in {"ablation", "both"}:
        scripts.append("run_ablation.py")

    print("=" * 72)
    print(f"🚀 Batch run start | mode={args.mode} | questions={len(question_files)}")
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
