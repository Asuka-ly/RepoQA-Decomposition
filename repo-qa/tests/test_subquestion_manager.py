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

    for i in range(5):
        manager.update(step=i + 1, action="ls", observation="", graph_hint="")

    assert manager.sub_questions[0]["status"] == "blocked"
    assert manager.check_replan_needed(step=5)
    snap = manager.snapshot()
    assert len(snap["replan_events"]) == 1


def test_subquestion_targeted_evidence_not_shared_blindly():
    manager = SubQuestionManager()
    manager.initialize(
        {
            "sub_questions": [
                {
                    "id": "SQ1",
                    "sub_question": "Where is parse_action implemented?",
                    "symbols": ["parse_action"],
                    "required_evidence": ["line number"],
                    "status": "open",
                    "progress": 0.0,
                    "attempts": 0,
                },
                {
                    "id": "SQ2",
                    "sub_question": "Where is setup.sh parsed?",
                    "symbols": ["setup_env_file"],
                    "required_evidence": ["line number"],
                    "status": "open",
                    "progress": 0.0,
                    "attempts": 0,
                },
            ]
        }
    )

    manager.update(
        step=1,
        action="nl -ba src/agent.py",
        observation="src/agent.py:42 def parse_action(action: str):",
        graph_hint="",
    )

    sq1, sq2 = manager.sub_questions
    assert len(sq1.get("evidence_found", [])) >= 1
    assert len(sq2.get("evidence_found", [])) == 0


def test_subquestion_rg_n_output_generates_reference():
    manager = SubQuestionManager()
    manager.initialize(
        {
            "sub_questions": [
                {
                    "id": "SQ1",
                    "sub_question": "Where is parse_action implemented?",
                    "symbols": ["parse_action"],
                    "required_evidence": ["line number"],
                    "entry_candidates": ["agents/default.py"],
                    "status": "open",
                    "progress": 0.0,
                    "attempts": 0,
                }
            ]
        }
    )

    manager.update(
        step=1,
        action='rg -n "def parse_action" agents/default.py',
        observation='116:    def parse_action(self, response):',
        graph_hint='',
    )

    sq = manager.sub_questions[0]
    assert 'agents/default.py:116' in sq.get('evidence_found', [])


def test_replan_trigger_on_no_new_evidence_steps():
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
                    "priority": 1,
                }
            ]
        }
    )

    # 第 1 步给一次证据，后续 3 步无新增证据
    manager.update(step=1, action="cat a.py", observation="a.py:10 A calls B", graph_hint="")
    manager.update(step=2, action="ls", observation="", graph_hint="")
    manager.update(step=3, action="ls", observation="", graph_hint="")
    manager.update(step=4, action="ls", observation="", graph_hint="")

    assert manager.check_replan_needed(step=4)
    assert any("no_new_evidence_for_3_steps" in e.get("reasons", []) for e in manager.replan_events)
