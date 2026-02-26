import json
from types import SimpleNamespace

from scripts.run_batch import resolve_question_files, _build_command


def test_resolve_question_files_defaults_to_q1_q4():
    files = resolve_question_files("", all_questions=False, source="stage1")
    assert len(files) == 4
    assert files[0].startswith("q1_")
    assert files[-1].startswith("q4_")


def test_resolve_question_files_from_csv():
    files = resolve_question_files("q1_timeout_exception.txt,q3_default_agent_action_flow.txt", all_questions=False)
    assert files == ["q1_timeout_exception.txt", "q3_default_agent_action_flow.txt"]


def test_resolve_question_files_from_swe_index(tmp_path):
    questions_dir = tmp_path / "questions"
    swe_dir = questions_dir / "swe_qa_bench"
    swe_dir.mkdir(parents=True)
    (swe_dir / "swe_qa_0001.txt").write_text("q1\n", encoding="utf-8")
    (swe_dir / "swe_qa_0002.txt").write_text("q2\n", encoding="utf-8")
    index = swe_dir / "index.jsonl"
    index.write_text(
        "\n".join(
            [
                json.dumps({"question_file": "swe_qa_bench/swe_qa_0001.txt"}),
                json.dumps({"question_file": "swe_qa_bench/swe_qa_0002.txt"}),
            ]
        ),
        encoding="utf-8",
    )

    files = resolve_question_files("", all_questions=False, source="swe_qa", questions_dir=questions_dir)
    assert files == ["swe_qa_bench/swe_qa_0001.txt", "swe_qa_bench/swe_qa_0002.txt"]


def test_resolve_question_files_from_swe_index_skips_invalid_and_normalizes(tmp_path):
    questions_dir = tmp_path / "questions"
    swe_dir = questions_dir / "swe_qa_bench"
    swe_dir.mkdir(parents=True)
    (swe_dir / "swe_qa_0001.txt").write_text("q1\n", encoding="utf-8")
    (swe_dir / "swe_qa_0002.txt").write_text("q2\n", encoding="utf-8")
    index = swe_dir / "index.jsonl"
    index.write_text(
        "\n".join(
            [
                "{broken-json}",
                json.dumps({"question_file": "swe_qa_0001.txt"}),
                json.dumps({"question_file": "swe_qa_bench/swe_qa_0001.txt"}),
                json.dumps({"question_file": "swe_qa_bench/swe_qa_0002.txt"}),
                json.dumps({"question_file": "swe_qa_bench/not_exists.txt"}),
            ]
        ),
        encoding="utf-8",
    )

    files = resolve_question_files("", all_questions=True, source="swe_qa", questions_dir=questions_dir)
    assert files == ["swe_qa_bench/swe_qa_0001.txt", "swe_qa_bench/swe_qa_0002.txt"]


def test_build_command_includes_mode_flags():
    args = SimpleNamespace(config="baseline", repo_path="/tmp/repo", offline=True, keep_proxy=True)
    cmd = _build_command("run_single.py", args, "q2_config_loading.txt")
    assert cmd[1] == "scripts/run_single.py"
    assert "--config" in cmd
    assert "--repo-path" in cmd
    assert "--offline" in cmd
    assert "--keep-proxy" in cmd
