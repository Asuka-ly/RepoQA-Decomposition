"""Dynamic replanning trigger evaluator.

Owner: planning
Boundary: trigger evaluation only.
"""
from __future__ import annotations

from src.planning.schema import ReplanDecision


class ReplanTriggerEvaluator:
    def __init__(self, stagnation_threshold: int = 3, min_coverage: float = 0.3):
        self.stagnation_threshold = stagnation_threshold
        self.min_coverage = min_coverage

    def evaluate(
        self,
        *,
        no_new_evidence_steps: int,
        evidence_coverage: float,
        unresolved_symbols: int,
    ) -> ReplanDecision:
        reasons: list[str] = []
        if no_new_evidence_steps >= self.stagnation_threshold:
            reasons.append("stagnation")
        if evidence_coverage < self.min_coverage:
            reasons.append("coverage")
        if unresolved_symbols > 0 and no_new_evidence_steps >= 2:
            reasons.append("evidence")

        return ReplanDecision(
            should_replan=bool(reasons),
            reasons=reasons,
            trigger_source="dynamic_trigger_v1",
        )
