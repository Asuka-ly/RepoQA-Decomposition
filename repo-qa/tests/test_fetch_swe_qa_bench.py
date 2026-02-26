import json
from pathlib import Path

from scripts.fetch_swe_qa_bench import collect_questions, materialize_questions


def test_collect_questions_from_jsonl_and_materialize(tmp_path: Path):
    repo = tmp_path / "dataset"
    repo.mkdir()
    data_file = repo / "bench_questions.jsonl"
    data_file.write_text(
        "\n".join(
            [
                json.dumps({"question": "Q1: where is parse_action defined?", "repo": "pallets/flask", "commit": "abc123"}),
                json.dumps({"prompt": "Q2: timeout flow?", "repo": "psf/requests", "commit": "def456"}),
                json.dumps({"other": "skip me"}),
            ]
        ),
        encoding="utf-8",
    )

    qs = collect_questions(repo, max_questions=10)
    assert len(qs) == 2
    assert qs[0]["question"].startswith("Q1")
    assert qs[0]["repo"] == "pallets/flask"
    assert qs[0]["commit"] == "abc123"

    out_dir = tmp_path / "questions_out"
    index = materialize_questions(qs, out_dir)
    assert index.exists()
    assert (out_dir / "swe_qa_0001.txt").exists()
    lines = [json.loads(x) for x in index.read_text(encoding="utf-8").strip().splitlines()]
    assert len(lines) == 2
    assert lines[0]["question_file"] == "swe_qa_bench/swe_qa_0001.txt"
    assert lines[0]["repo"] == "pallets/flask"


def test_collect_questions_from_nested_json(tmp_path: Path):
    repo = tmp_path / "dataset"
    repo.mkdir()
    data_file = repo / "qa_dataset.json"
    data_file.write_text(
        json.dumps(
            {
                "data": [
                    {"meta": {"query": "Q1 nested query"}},
                    {"instruction": "Q2 instruction"},
                ]
            }
        ),
        encoding="utf-8",
    )

    qs = collect_questions(repo, max_questions=10)
    assert len(qs) == 2
    assert "nested query" in qs[0]["question"]


def test_collect_questions_from_markdown_fallback(tmp_path: Path):
    repo = tmp_path / "dataset"
    repo.mkdir()
    md = repo / "README.md"
    md.write_text("Some intro\nWhat is timeout behavior?\nNot a question\n", encoding="utf-8")

    qs = collect_questions(repo, max_questions=10)
    assert len(qs) == 1
    assert "timeout" in qs[0]["question"].lower()
