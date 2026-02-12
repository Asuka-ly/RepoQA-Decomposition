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

    def _fake(task):
        called["n"] += 1
        return True

    agent._run_decompose_tool = _fake
    agent._maybe_bootstrap_decompose_from_action("rg -n parse_action agents/default.py", step=0)
    assert called["n"] == 1
