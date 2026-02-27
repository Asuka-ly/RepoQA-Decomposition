from types import SimpleNamespace

from src.planning.replanner import ReplanTriggerEvaluator


def test_replan_trigger_on_stagnation_and_coverage():
    evaluator = ReplanTriggerEvaluator(stagnation_threshold=3, min_coverage=0.5)
    decision = evaluator.evaluate(no_new_evidence_steps=3, evidence_coverage=0.2, unresolved_symbols=1)
    assert decision.should_replan is True
    assert "stagnation" in decision.reasons
    assert "coverage" in decision.reasons
