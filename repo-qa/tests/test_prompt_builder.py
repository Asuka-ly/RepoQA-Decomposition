from src.utils import build_task_prompt


class _Cfg:
    enable_decomposition_tool = True
    decompose_on_start = False
    enable_graph_injection = True
    enable_graph_tools = True


def test_prompt_contains_tool_usage_playbook():
    text = build_task_prompt(
        task="Where is parse_action defined?",
        repo_path="/tmp/repo",
        decomposition=None,
        config=_Cfg(),
    )
    assert "TOOL USAGE PLAYBOOK" in text
    assert "DECOMPOSE_WITH_GRAPH" in text
    assert "GRAPH_RETRIEVE" in text
