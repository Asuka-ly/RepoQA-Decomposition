"""轨迹质量分析脚本

用于快速检查 run_single/run_ablation 产出的 full_log.json：
- 是否有最终答案
- 是否包含文件:行号证据
- 子问题完成度与 replan 统计
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict


def load_latest_trajectory(base: Path, config_name: str) -> Path:
    target = base / "experiments" / "comparison_reports" / "trajectories" / config_name
    if not target.exists():
        raise FileNotFoundError(f"trajectory dir not found: {target}")
    files = sorted(target.glob("*_full_log.json"))
    if not files:
        raise FileNotFoundError(f"no trajectory files in: {target}")
    return files[-1]


def analyze(data: Dict[str, Any]) -> Dict[str, Any]:
    answer = data.get("final_answer") or ""
    stats = data.get("statistics", {})
    trace = data.get("subquestion_trace", {})
    sub_questions = trace.get("sub_questions", [])
    replan_events = trace.get("replan_events", [])

    answer_refs = set(re.findall(r"\b[\w/.-]+\.py:\d+\b", answer))
    trace_refs = set()
    for sq in sub_questions:
        for ref in sq.get("evidence_found", []) or []:
            if isinstance(ref, str) and re.match(r"^[\w/.-]+\.py:(\d+|nl)$", ref):
                trace_refs.add(ref)

    evidence_refs = answer_refs | trace_refs
    has_final_answer = isinstance(answer, str) and len(answer.strip()) > 0 and not answer.startswith("ERROR:")

    satisfied = sum(1 for sq in sub_questions if sq.get("status") == "satisfied")
    blocked = sum(1 for sq in sub_questions if sq.get("status") == "blocked")

    quality_flags = {
        "missing_final_answer": not has_final_answer,
        "missing_evidence_refs": len(evidence_refs) == 0,
        "no_code_reads": (stats.get("viewed_files", 0) or 0) == 0,
    }

    return {
        "total_steps": stats.get("total_steps", 0),
        "viewed_files": stats.get("viewed_files", 0),
        "has_final_answer": has_final_answer,
        "answer_length": len(answer),
        "evidence_ref_count": len(evidence_refs),
        "sub_questions_total": len(sub_questions),
        "sub_questions_satisfied": satisfied,
        "sub_questions_blocked": blocked,
        "replan_events": len(replan_events),
        "quality_flags": quality_flags,
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze RepoQA trajectory quality")
    parser.add_argument("--config", default="baseline", help="trajectory config folder name")
    parser.add_argument("--file", default=None, help="explicit trajectory json file")
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent
    traj_file = Path(args.file) if args.file else load_latest_trajectory(base, args.config)

    data = json.loads(traj_file.read_text(encoding="utf-8"))
    result = analyze(data)

    print("=" * 60)
    print(f"Trajectory: {traj_file}")
    print("=" * 60)
    for k, v in result.items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
