from scripts.analyze_trajectory import analyze


def test_analyze_reports_decomposition_action_metadata_and_posterior():
    data = {
        "statistics": {"total_steps": 3, "viewed_files": 1},
        "final_answer": "parse_action in agents/default.py:116",
        "decomposition_action": {
            "quality": {"overall": 0.82},
            "decomposition": {"action_metadata": {"contract_version": "stage1_v2.2"}},
        },
        "trajectory_schema_version": "stage1_v2.3",
        "tool_calls": [{"tool_name": "DECOMPOSE_WITH_GRAPH"}, {"tool_name": "GRAPH_RETRIEVE"}],
        "subquestion_trace": {
            "sub_questions": [
                {"status": "satisfied", "symbols": ["parse_action"], "evidence_found": ["agents/default.py:116"]}
            ],
            "replan_events": [],
            "quality_history": [{"step": 1, "score": 0.7}],
        },
    }
    result = analyze(data)
    assert result["decomposition_quality"] == 0.82
    assert result["decomposition_contract_version"] == "stage1_v2.2"
    assert result["posterior_quality"]["completion_rate"] == 1.0
    assert result["posterior_quality"]["answer_alignment"] == 1.0



def test_analyze_reports_tool_call_summary():
    data = {
        "trajectory_schema_version": "stage1_v2.3",
        "statistics": {"total_steps": 2, "viewed_files": 1},
        "final_answer": "ok a.py:1",
        "tool_calls": [
            {"tool_name": "DECOMPOSE_WITH_GRAPH"},
            {"tool_name": "GRAPH_RETRIEVE"},
            {"tool_name": "GRAPH_RETRIEVE"},
        ],
        "subquestion_trace": {"sub_questions": [], "replan_events": [], "quality_history": []},
    }
    result = analyze(data)
    assert result["trajectory_schema_version"] == "stage1_v2.3"
    assert result["tool_call_count"] == 3
    assert result["tool_call_counter"]["GRAPH_RETRIEVE"] == 2
