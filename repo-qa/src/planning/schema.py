"""Planning tool schemas.

Owner: planning
Boundary: plan I/O schema only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PlanSubQuestion:
    id: str
    sub_question: str
    hypothesis: str
    entry_candidates: list[str]
    symbols: list[str]
    required_evidence: list[str]
    exit_criterion: str
    status: str = "open"
    priority: int = 1


@dataclass
class Plan:
    schema_version: str = "decomposition_plan.v1"
    sub_questions: list[PlanSubQuestion] = field(default_factory=list)
    synthesis: str = ""
    estimated_hops: int = 1
    unresolved_symbols: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReplanDecision:
    should_replan: bool
    reasons: list[str]
    trigger_source: str
