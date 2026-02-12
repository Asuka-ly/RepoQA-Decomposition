from src.agents.base import BaseRepoQAAgent


class _DummySubq:
    def __init__(self):
        self.sub_questions = [
            {
                "id": "SQ1",
                "status": "satisfied",
                "sub_question": "where is parse_action",
                "evidence_found": ["agents/default.py:116"],
            }
        ]


def test_extract_final_answer_falls_back_to_history_summary():
    agent = BaseRepoQAAgent.__new__(BaseRepoQAAgent)
    agent.messages = [
        {"role": "system", "content": "x"},
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": "intermediate notes"},
        {"role": "user", "content": "obs agents/default.py:116"},
    ]
    agent.subq_manager = _DummySubq()

    ans = agent._extract_final_answer()
    assert "[SUMMARY]" in ans
    assert "agents/default.py:116" in ans
    assert "SQ1" in ans
