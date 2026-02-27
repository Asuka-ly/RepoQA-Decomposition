from src.contracts import SWEQAAdapter


def test_adapter_returns_valid_record():
    adapter = SWEQAAdapter()
    out = adapter.adapt({"question": "How does parser work?", "repo": "org/repo", "commit": "abc123", "instance_id": "1"})
    assert out.repo == "org/repo"
    assert out.commit == "abc123"


def test_adapter_rejects_markdown_question():
    adapter = SWEQAAdapter()
    out = adapter.adapt({"question": "```markdown", "repo": "org/repo", "commit": "abc"})
    assert out.reason_code == "invalid_question"
