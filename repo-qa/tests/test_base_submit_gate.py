from src.agents.base import BaseRepoQAAgent


class _DummySubq:
    def __init__(self, sub_questions):
        self.sub_questions = sub_questions


def _mk_agent(messages, viewed_files, subq=None):
    agent = BaseRepoQAAgent.__new__(BaseRepoQAAgent)
    agent.messages = messages
    agent.viewed_files = set(viewed_files)
    agent.subq_manager = subq
    return agent


def test_can_submit_vanilla_requires_traceable_evidence():
    agent = _mk_agent(
        messages=[
            {"role": "system", "content": "x"},
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "read file"},
            {"role": "user", "content": "no ref"},
            {"role": "assistant", "content": "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"},
        ],
        viewed_files={"agents/default.py"},
        subq=None,
    )
    assert agent._can_submit() is False


def test_can_submit_vanilla_passes_with_evidence_ref_and_steps():
    agent = _mk_agent(
        messages=[
            {"role": "system", "content": "x"},
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "agents/default.py:116"},
            {"role": "user", "content": "ok"},
            {"role": "assistant", "content": "more"},
            {"role": "user", "content": "obs"},
            {"role": "assistant", "content": "mid"},
            {"role": "user", "content": "obs2"},
            {"role": "assistant", "content": "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"},
        ],
        viewed_files={"agents/default.py"},
        subq=None,
    )
    assert agent._can_submit() is True


def test_can_submit_strategic_needs_satisfied_and_evidence():
    subq = _DummySubq(
        [
            {"status": "satisfied", "progress": 0.8, "evidence_found": ["a.py:10"]},
            {"status": "in_progress", "progress": 0.7, "evidence_found": []},
            {"status": "satisfied", "progress": 1.0, "evidence_found": ["b.py:20"]},
        ]
    )
    agent = _mk_agent(
        messages=[
            {"role": "system", "content": "x"},
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "a.py:10"},
            {"role": "user", "content": "obs1"},
            {"role": "assistant", "content": "b.py:20"},
            {"role": "user", "content": "obs2"},
            {"role": "assistant", "content": "final"},
            {"role": "user", "content": "obs3"},
        ],
        viewed_files={"a.py", "b.py"},
        subq=subq,
    )
    assert agent._can_submit() is True


def test_submit_command_must_be_standalone():
    agent = _mk_agent(messages=[], viewed_files=set(), subq=None)
    assert agent._is_submit_signal("cat a.py && echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT") is True
    assert agent._is_standalone_submit_command("cat a.py && echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT") is False
    assert agent._is_standalone_submit_command("echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT") is True
