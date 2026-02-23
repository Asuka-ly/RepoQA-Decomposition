from src.tool_registry import ToolRegistry


def test_tool_registry_records_success_call():
    registry = ToolRegistry()

    out = registry.invoke(
        step=1,
        tool_name="GRAPH_RETRIEVE",
        reason="unit_test",
        fn=lambda: {"grounded": 1},
        input_obj={"symbols": ["A"]},
    )

    assert out["grounded"] == 1
    calls = registry.get_calls()
    assert len(calls) == 1
    assert calls[0]["tool_name"] == "GRAPH_RETRIEVE"
    assert calls[0]["success"] is True
    assert registry.get_counters()["GRAPH_RETRIEVE"] == 1


def test_tool_registry_records_error_call():
    registry = ToolRegistry()

    def _boom():
        raise RuntimeError("x")

    try:
        registry.invoke(
            step=2,
            tool_name="DECOMPOSE_WITH_GRAPH",
            reason="unit_test",
            fn=_boom,
            input_obj={"task": "q"},
        )
    except RuntimeError:
        pass

    calls = registry.get_calls()
    assert len(calls) == 1
    assert calls[0]["success"] is False
    assert calls[0]["error"] == "x"
