from types import SimpleNamespace

from src.agents.strategic_agent import StrategicRepoQAAgent


def _mk_agent(enable_graph_tools=True, enable_dynamic_graph_tool_calls=True, decompose_on_start=False, enable_decomposition_tool=True):
    agent = StrategicRepoQAAgent.__new__(StrategicRepoQAAgent)
    agent.exp_config = SimpleNamespace(
        enable_graph_tools=enable_graph_tools,
        enable_dynamic_graph_tool_calls=enable_dynamic_graph_tool_calls,
        graph_tool_stagnation_steps=2,
        decompose_on_start=decompose_on_start,
        enable_decomposition_tool=enable_decomposition_tool,
        tool_result_detail_level="hybrid",
    )
    agent.graph_tools = object()
    agent.decomposition = None
    agent.messages = [{"role": "system", "content": "x"}, {"role": "user", "content": "task"}]
    agent.subq_manager = SimpleNamespace(no_new_evidence_steps=0, sub_questions=[])
    return agent


def test_should_call_graph_tool_respects_disable_switch():
    agent = _mk_agent(enable_graph_tools=False)
    assert agent._should_call_graph_tool("rg -n foo bar.py", step=1) is False


def test_should_call_graph_tool_lookup_action_when_enabled():
    agent = _mk_agent(enable_graph_tools=True, enable_dynamic_graph_tool_calls=False)
    assert agent._should_call_graph_tool("rg -n parse_action agents/default.py", step=1) is True


def test_lazy_decompose_bootstrap_calls_tool_once(monkeypatch):
    agent = _mk_agent(decompose_on_start=False, enable_decomposition_tool=True)
    called = {"n": 0}

    def _fake(task, step=0, reason=""):
        called["n"] += 1
        return True

    agent._run_decompose_tool = _fake
    agent._maybe_bootstrap_decompose_from_action("rg -n parse_action agents/default.py", step=0)
    assert called["n"] == 1


def test_lazy_decompose_bootstrap_skips_broad_scan_script():
    agent = _mk_agent(decompose_on_start=False, enable_decomposition_tool=True)
    called = {"n": 0}

    def _fake(task, step=0, reason=""):
        called["n"] += 1
        return True

    agent._run_decompose_tool = _fake
    agent._maybe_bootstrap_decompose_from_action(
        "cd repo && find . -name '*.py' | while read -r f; do nl -ba $f; done",
        step=0,
    )
    assert called["n"] == 0


def test_build_graph_action_hints_from_retrieve_result():
    agent = _mk_agent()
    hints = agent._build_graph_action_hints({
        "results": {
            "parse_action": [
                {"file": "agents/default.py", "line": 116, "qname": "DefaultAgent.parse_action"}
            ]
        }
    })
    assert any("rg -n" in h for h in hints)
    assert any("nl -ba agents/default.py" in h for h in hints)


def test_relation_replan_needed_when_metrics_bad_and_stagnant():
    agent = _mk_agent()
    agent.decomposition_quality = {
        "relation": {
            "overlap_balance": 0.2,
            "completeness_proxy": 0.4,
        }
    }
    agent.subq_manager = SimpleNamespace(no_new_evidence_steps=2, sub_questions=[])
    assert agent._relation_replan_needed() is True


def test_manual_tool_call_retrieve_updates_unresolved_cooldown():
    agent = _mk_agent()
    agent.tool_registry = SimpleNamespace(invoke=lambda **kwargs: {"results": {"foo": []}, "grounded": 0, "retrieval_mode": "ast_only"})
    agent.graph_tools = SimpleNamespace()
    agent.unresolved_symbol_cooldown = {}
    out = agent._handle_tool_call_command('TOOL_CALL GRAPH_RETRIEVE {"symbols":["foo"]}')
    assert out["returncode"] == 0
    assert "[TOOL] GRAPH_RETRIEVE" in out["output"]
    assert "[TOOL_DETAIL_JSON]" in out["output"]
    assert agent.unresolved_symbol_cooldown.get("foo") is not None


def test_base_tool_call_command_parser():
    from src.agents.base import BaseRepoQAAgent

    agent = BaseRepoQAAgent.__new__(BaseRepoQAAgent)
    assert agent._is_tool_call_command('TOOL_CALL GRAPH_RETRIEVE {"symbols":["x"]}') is True
    assert agent._is_tool_call_command('rg -n x foo.py') is False


def test_tool_result_summary_mode_strips_detail_json():
    agent = _mk_agent()
    agent.exp_config.tool_result_detail_level = "summary"
    agent.tool_registry = SimpleNamespace(invoke=lambda **kwargs: {"results": {"foo": [{"file": "a.py", "line": 1}]}, "grounded": 1, "retrieval_mode": "ast_only"})
    agent.graph_tools = SimpleNamespace()
    agent.unresolved_symbol_cooldown = {}
    out = agent._handle_tool_call_command('TOOL_CALL GRAPH_RETRIEVE {"symbols":["foo"]}')
    assert "[TOOL] GRAPH_RETRIEVE" in out["output"]
    assert "[TOOL_DETAIL_JSON]" not in out["output"]
