import json

from scripts.fetch_swe_qa_bench import collect_questions


def test_collect_questions_filters_invalid_and_counts_reasons(tmp_path):
    data = [
        {"question": "How to fix parser?", "repo": "a/b", "commit": "abc", "instance_id": "i1"},
        {"question": "```markdown", "repo": "a/b", "commit": "abc", "instance_id": "i2"},
        {"question": "How to load config?", "repo": "a/b", "instance_id": "i3"},
    ]
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    rows, reasons = collect_questions(tmp_path, max_questions=10)

    assert len(rows) == 1
    assert rows[0]["repo"] == "a/b"
    assert reasons["invalid_question"] == 1
    assert reasons["missing_commit"] == 1
