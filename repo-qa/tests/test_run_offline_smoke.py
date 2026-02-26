from scripts.run_offline_smoke import _strategic_outputs, _vanilla_outputs


def test_offline_smoke_outputs_have_enough_steps_for_submit_gate():
    outputs = _strategic_outputs('/tmp/repo')
    assert len(outputs) >= 6
    assert 'echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT' in outputs[-1]
    assert outputs[-1].count('agents/default.py:') >= 2


def test_offline_smoke_vanilla_answer_has_multiple_refs():
    outputs = _vanilla_outputs('/tmp/repo')
    assert len(outputs) >= 5
    assert outputs[-1].count('agents/default.py:') >= 2
