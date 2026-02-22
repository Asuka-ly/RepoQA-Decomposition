from src.decomposition_action import (
    DecompositionAction,
    CONTRACT_VERSION,
    REQUIRED_SUBQ_FIELDS,
    DEFAULT_REPLAN_TRIGGERS,
)


class _StubDecomposer:
    def __init__(self, payload, graph=None):
        self.payload = payload
        self.code_graph = graph

    def decompose(self, question: str):
        return self.payload


class _StubGraph:
    def search_symbol(self, keyword: str, limit: int = 5):
        if keyword in {"parse_action", "DefaultAgent"}:
            return [{"name": keyword, "qname": keyword, "file": "agents/default.py", "line": 116, "type": "function"}]
        return []


def test_decomposition_action_attach_metadata_and_quality():
    payload = {
        "sub_questions": [
            {
                "id": "SQ1",
                "sub_question": "Where is parse_action defined?",
                "entry_candidates": ["agents/default.py::DefaultAgent.parse_action"],
                "symbols": ["parse_action"],
                "required_evidence": ["definition location", "call path"],
            }
        ]
    }
    action = DecompositionAction(_StubDecomposer(payload, graph=_StubGraph()))
    result = action.execute("dummy question")

    assert result.quality["overall"] > 0
    assert result.decomposition["action_metadata"]["action_name"] == "DECOMPOSE_WITH_GRAPH"
    assert result.decomposition["action_metadata"]["contract_version"] == CONTRACT_VERSION
    assert result.workflow_trace[0]["step"] == "decompose"
    assert "penalties" in result.quality


def test_decomposition_action_quality_zero_on_empty_subq():
    payload = {"sub_questions": []}
    action = DecompositionAction(_StubDecomposer(payload))
    result = action.execute("dummy")

    assert result.quality["overall"] == 0.0


def test_decomposition_action_freezes_required_subq_fields_and_contract_keys():
    payload = {
        "sub_questions": [
            {
                "sub_question": "Q1?",
                "entry_candidates": [],
            }
        ]
    }
    action = DecompositionAction(_StubDecomposer(payload))
    result = action.execute("dummy")

    sq = result.decomposition["sub_questions"][0]
    for field in REQUIRED_SUBQ_FIELDS:
        assert field in sq

    assert "plan_order" in result.decomposition
    assert "evidence_requirements" in result.decomposition
    assert "quality_estimate" in result.decomposition
    assert result.decomposition["replan_triggers"] == DEFAULT_REPLAN_TRIGGERS


def test_decomposition_action_quality_contains_relation_metrics():
    payload = {
        "sub_questions": [
            {
                "id": "SQ1",
                "sub_question": "Where parse_action is defined?",
                "entry_candidates": ["agents/default.py::DefaultAgent.parse_action"],
                "symbols": ["parse_action", "DefaultAgent"],
                "required_evidence": ["definition location", "call path"],
                "priority": 1,
            },
            {
                "id": "SQ2",
                "sub_question": "How execute_action handles timeout?",
                "entry_candidates": ["agents/default.py::DefaultAgent.execute_action"],
                "symbols": ["execute_action", "DefaultAgent"],
                "required_evidence": ["exception path", "raise location"],
                "priority": 2,
            },
        ],
        "unresolved_symbols": [],
    }
    action = DecompositionAction(_StubDecomposer(payload, graph=_StubGraph()))
    result = action.execute("dummy question")

    rel = result.quality["relation"]
    assert "symbol_overlap" in rel
    assert "dependency_signal" in rel
    assert "completeness_proxy" in rel
    assert "overlap_balance" in rel
