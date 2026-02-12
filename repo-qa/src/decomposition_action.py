"""Stage1 v2.0: 问题分解 Action/Tool 封装

目标：将分解从“初始化中的 thought-like 步骤”提升为可观测、可评估的独立 Action。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List

from src.decomposer import StrategicDecomposer
from src.graph_tools import GraphTools


CONTRACT_VERSION = "stage1_v2.2"
REQUIRED_SUBQ_FIELDS = [
    "id",
    "sub_question",
    "hypothesis",
    "entry_candidates",
    "symbols",
    "required_evidence",
    "exit_criterion",
    "status",
    "priority",
    "evidence_found",
    "progress",
    "attempts",
]
DEFAULT_REPLAN_TRIGGERS = [
    "no_new_evidence_for_3_steps",
    "high_priority_stagnation",
    "decomposition_quality_drop",
    "blocked_sub_questions_detected",
]


@dataclass
class DecompositionActionResult:
    decomposition: Dict[str, Any]
    quality: Dict[str, Any]
    workflow_trace: List[Dict[str, Any]]


class DecompositionAction:
    """问题分解独立 Action。"""

    def __init__(self, decomposer: StrategicDecomposer):
        self.decomposer = decomposer
        self.graph_tools = GraphTools(getattr(decomposer, "code_graph", None))

    def execute(self, question: str) -> DecompositionActionResult:
        raw = self.decomposer.decompose(question)
        decomposition = self._freeze_contract(raw)
        quality = self._estimate_quality(decomposition)

        decomposition["quality_estimate"] = quality

        decomposition.setdefault("action_metadata", {})
        decomposition["action_metadata"].update(
            {
                "action_name": "DECOMPOSE_WITH_GRAPH",
                "quality": quality,
                "contract_version": CONTRACT_VERSION,
                "required_subq_fields": REQUIRED_SUBQ_FIELDS,
            }
        )

        workflow_trace = [
            {
                "step": "decompose",
                "action": "DECOMPOSE_WITH_GRAPH",
                "sub_questions": len(decomposition.get("sub_questions", [])),
                "quality_score": quality.get("overall", 0.0),
                "contract_version": CONTRACT_VERSION,
            }
        ]

        return DecompositionActionResult(
            decomposition=decomposition,
            quality=quality,
            workflow_trace=workflow_trace,
        )

    def _freeze_contract(self, decomposition: Dict[str, Any]) -> Dict[str, Any]:
        """冻结分解 Action 的输出契约，确保下游字段稳定。"""
        subq = decomposition.get("sub_questions") or []
        frozen_items: List[Dict[str, Any]] = []
        for idx, item in enumerate(subq, 1):
            frozen_items.append(
                {
                    "id": item.get("id", f"SQ{idx}"),
                    "sub_question": item.get("sub_question", "Unknown sub-question"),
                    "hypothesis": item.get("hypothesis", "To be validated from code evidence"),
                    "entry_candidates": (item.get("entry_candidates") or ["unknown"]),
                    "symbols": item.get("symbols") or [],
                    "required_evidence": item.get("required_evidence") or ["definition location", "call path"],
                    "exit_criterion": item.get("exit_criterion", "At least one grounded code evidence item"),
                    "status": item.get("status", "open"),
                    "priority": item.get("priority", idx),
                    "evidence_found": item.get("evidence_found") or [],
                    "progress": float(item.get("progress", 0.0)),
                    "attempts": int(item.get("attempts", 0)),
                }
            )

        frozen_items = sorted(frozen_items, key=lambda x: x.get("priority", 999))
        decomposition["sub_questions"] = frozen_items
        decomposition["plan_order"] = [x["id"] for x in frozen_items]
        decomposition["evidence_requirements"] = {
            x["id"]: list(x.get("required_evidence", [])) for x in frozen_items
        }
        decomposition["replan_triggers"] = list(DEFAULT_REPLAN_TRIGGERS)

        decomposition.setdefault("synthesis", "Synthesize validated sub-question evidence")
        decomposition.setdefault("estimated_hops", max(1, len(frozen_items)))
        decomposition.setdefault("unresolved_symbols", [])
        return decomposition

    def _estimate_quality(self, decomposition: Dict[str, Any]) -> Dict[str, Any]:
        subq = decomposition.get("sub_questions", []) or []
        if not subq:
            return {
                "overall": 0.0,
                "prior": {
                    "graph_grounding_coverage": 0.0,
                    "entry_executability": 0.0,
                    "subq_uniqueness": 0.0,
                },
                "penalties": {
                    "duplicate_subq_penalty": 0.0,
                    "generic_entry_penalty": 0.0,
                },
                "posterior": {
                    "evidence_yield": 0.0,
                    "completion_rate": 0.0,
                    "answer_alignment": 0.0,
                },
            }

        total = len(subq)
        validation = self.graph_tools.graph_validate(subq)

        unique_questions = {x.get("sub_question", "").strip().lower() for x in subq}
        uniqueness = len(unique_questions) / total
        duplicate_penalty = round(1.0 - uniqueness, 4)

        generic_entries = 0
        total_entries = 0
        for sq in subq:
            for entry in sq.get("entry_candidates", []):
                if not isinstance(entry, str):
                    continue
                total_entries += 1
                if entry.strip().lower() in {"unknown", "unknown.py::unknown", "unknown::unknown"}:
                    generic_entries += 1
        generic_entry_penalty = round((generic_entries / total_entries), 4) if total_entries else 1.0

        prior = {
            "graph_grounding_coverage": validation.get("grounding_coverage", 0.0),
            "entry_executability": validation.get("executable_entry_rate", 0.0),
            "subq_uniqueness": round(uniqueness, 4),
        }
        penalties = {
            "duplicate_subq_penalty": duplicate_penalty,
            "generic_entry_penalty": generic_entry_penalty,
        }

        # explainable weighted score
        prior_base = (
            0.45 * prior["graph_grounding_coverage"]
            + 0.35 * prior["entry_executability"]
            + 0.20 * prior["subq_uniqueness"]
        )
        penalty = 0.15 * penalties["duplicate_subq_penalty"] + 0.15 * penalties["generic_entry_penalty"]
        overall = round(max(0.0, prior_base - penalty), 4)

        return {
            "overall": overall,
            "prior": prior,
            "penalties": penalties,
            "posterior": {
                "evidence_yield": 0.0,
                "completion_rate": 0.0,
                "answer_alignment": 0.0,
            },
            "sub_questions": total,
            "graph_validation": validation,
        }
