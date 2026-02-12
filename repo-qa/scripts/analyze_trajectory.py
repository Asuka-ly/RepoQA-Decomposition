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
    quality_history = trace.get("quality_history", []) or []

    decomp_action = data.get("decomposition_action", {})
    decomp_quality = (decomp_action.get("quality") or {}) if isinstance(decomp_action, dict) else {}
    if not decomp_quality and isinstance(stats.get("decomposition_quality"), (float, int)):
        decomp_quality = {"overall": float(stats.get("decomposition_quality"))}
    decomp_meta = ((decomp_action.get("decomposition") or {}).get("action_metadata") or {}) if isinstance(decomp_action, dict) else {}

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

    # 后验质量：执行过程统计
    total_subq = len(sub_questions)
    completion_rate = round((satisfied / total_subq), 4) if total_subq else 0.0
    evidence_yield = round((len(trace_refs) / max(1, total_subq)), 4) if total_subq else 0.0

    answer_lower = answer.lower()
    align_hits = 0
    for sq in sub_questions:
        symbols = [s.lower() for s in sq.get("symbols", []) if isinstance(s, str)]
        if symbols and any(sym in answer_lower for sym in symbols):
            align_hits += 1
    answer_alignment = round((align_hits / total_subq), 4) if total_subq else 0.0

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
        "sub_questions_total": total_subq,
        "sub_questions_satisfied": satisfied,
        "sub_questions_blocked": blocked,
        "replan_events": len(replan_events),
        "decomposition_quality": decomp_quality.get("overall", None),
        "decomposition_contract_version": decomp_meta.get("contract_version", None),
        "posterior_quality": {
            "evidence_yield": evidence_yield,
            "completion_rate": completion_rate,
            "answer_alignment": answer_alignment,
            "latest_live_quality": quality_history[-1]["score"] if quality_history else None,
        },
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
