from src.subquestion_manager import SubQuestionManager


def test_subquestion_update_progress_and_status():
    manager = SubQuestionManager()
    manager.initialize(
        {
            "sub_questions": [
                {
                    "id": "SQ1",
                    "sub_question": "How does A call B?",
                    "symbols": ["A", "B"],
                    "required_evidence": ["definition location", "call path"],
                    "status": "open",
                    "progress": 0.0,
                    "attempts": 0,
                }
            ]
        }
    )

    manager.update(
        step=1,
        action="cat a.py",
        observation="a.py:10 function A calls B",
        graph_hint="[GRAPH HINT] A -> B",
    )

    sq = manager.sub_questions[0]
    assert sq["status"] in {"in_progress", "satisfied"}
    assert sq["progress"] > 0
    assert len(manager.transitions) == 1


def test_subquestion_blocked_when_no_progress():
    manager = SubQuestionManager()
    manager.initialize(
        {
            "sub_questions": [
                {
                    "id": "SQ1",
                    "sub_question": "How does A call B?",
                    "symbols": ["A", "B"],
                    "required_evidence": ["definition location", "call path"],
                    "status": "open",
                    "progress": 0.0,
                    "attempts": 0,
                }
            ]
        }
    )

    for i in range(4):
        manager.update(step=i + 1, action="ls", observation="", graph_hint="")

    assert manager.sub_questions[0]["status"] == "blocked"
    assert manager.check_replan_needed(step=5)
    snap = manager.snapshot()
    assert len(snap["replan_events"]) == 1
