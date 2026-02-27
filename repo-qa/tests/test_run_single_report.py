from scripts.run_single import _build_unified_report


class _Agent:
    def _get_stats(self):
        return {
            "telemetry": {"evidence_coverage": 0.3, "completion_rate": 0.5},
            "tool_call_counters": {"GRAPH_RETRIEVE": 2},
            "decompose_tool_calls": 1,
            "replan_events": 1,
        }

    class decision_trace:
        @staticmethod
        def to_dict():
            return {"schema_version": "decision_trace.v1", "events": []}


def test_build_unified_report_contains_required_fields():
    report = _build_unified_report(_Agent(), {"repo": "x", "commit": "y"}, "q.txt")
    assert report["decompose_calls"] == 1
    assert "decision_trace" in report
    assert "telemetry" in report
