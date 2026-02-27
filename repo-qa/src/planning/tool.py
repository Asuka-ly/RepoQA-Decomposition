"""Independent decomposition tool package.

Owner: planning
Boundary: wraps decomposition/graph/replanner and returns strict plan schema.
"""
from __future__ import annotations

from src.decomposition_action import DecompositionAction
from src.decomposer import StrategicDecomposer
from src.graph_tools import GraphTools
from src.planning.replanner import ReplanTriggerEvaluator
from src.planning.schema import Plan, PlanSubQuestion, ReplanDecision


class DecompositionPlanningTool:
    schema_version = "decomposition_tool.v1"

    def __init__(self, model, code_graph):
        self.decomposer = StrategicDecomposer(model, code_graph)
        self.action = DecompositionAction(self.decomposer)
        self.graph_tools = GraphTools(code_graph)
        self.replan = ReplanTriggerEvaluator()

    def decompose(self, question: str) -> tuple[Plan, dict]:
        result = self.action.execute(question)
        sub_questions = [
            PlanSubQuestion(
                id=item["id"],
                sub_question=item["sub_question"],
                hypothesis=item["hypothesis"],
                entry_candidates=list(item.get("entry_candidates", [])),
                symbols=list(item.get("symbols", [])),
                required_evidence=list(item.get("required_evidence", [])),
                exit_criterion=item.get("exit_criterion", ""),
                status=item.get("status", "open"),
                priority=int(item.get("priority", 1)),
            )
            for item in result.decomposition.get("sub_questions", [])
        ]
        plan = Plan(
            sub_questions=sub_questions,
            synthesis=result.decomposition.get("synthesis", ""),
            estimated_hops=int(result.decomposition.get("estimated_hops", 1)),
            unresolved_symbols=list(result.decomposition.get("unresolved_symbols", [])),
        )
        metadata = {
            "quality": result.quality,
            "workflow_trace": result.workflow_trace,
            "tool_schema_version": self.schema_version,
        }
        return plan, metadata

    def should_replan(self, *, no_new_evidence_steps: int, evidence_coverage: float, unresolved_symbols: int) -> ReplanDecision:
        return self.replan.evaluate(
            no_new_evidence_steps=no_new_evidence_steps,
            evidence_coverage=evidence_coverage,
            unresolved_symbols=unresolved_symbols,
        )
