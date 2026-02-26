from src.graph_tools import GraphTools


class _StubGraph:
    def search_symbol(self, keyword: str, limit: int = 5):
        if keyword == "parse_action":
            return [{"qname": "DefaultAgent.parse_action", "file": "agents/default.py", "line": 116, "type": "function"}]
        return []


def test_graph_retrieve_and_validate():
    tools = GraphTools(_StubGraph())
    r = tools.graph_retrieve(["parse_action", "unknown"])
    assert r["grounded"] == 1

    val = tools.graph_validate(
        [
            {
                "id": "SQ1",
                "symbols": ["parse_action"],
                "entry_candidates": ["agents/default.py::DefaultAgent.parse_action"],
            },
            {
                "id": "SQ2",
                "symbols": ["unknown"],
                "entry_candidates": ["unknown"],
            },
        ]
    )
    assert val["grounding_coverage"] == 0.5
    assert val["executable_entry_rate"] == 0.5


class _StubGraphWithFiles:
    def __init__(self):
        self.file_contents = {
            "agents/default.py": """def dynamic_exec():
    return run_dynamic_timeout()
"""
        }

    def search_symbol(self, keyword: str, limit: int = 5):
        return []


def test_graph_retrieve_lexical_fallback_when_ast_misses():
    tools = GraphTools(_StubGraphWithFiles())
    r = tools.graph_retrieve(["run_dynamic_timeout"])
    assert r["grounded"] == 1
    assert r["fallback_hits"] == 1
    assert r["retrieval_mode"] == "ast+lexical"
