import json
from pathlib import Path

from scripts import run_single


def test_load_question_metadata_from_index(tmp_path, monkeypatch):
    repo_qa_root = tmp_path / "repo-qa"
    qdir = repo_qa_root / "data" / "questions" / "swe_qa_bench"
    qdir.mkdir(parents=True)

    qf = qdir / "swe_qa_0001.txt"
    qf.write_text("What is this?\n", encoding="utf-8")
    (qdir / "index.jsonl").write_text(
        json.dumps(
            {
                "question_file": "swe_qa_bench/swe_qa_0001.txt",
                "repo": "pallets/flask",
                "commit": "abc123",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(run_single.PATH_CONFIG, "repo_qa_root", repo_qa_root)
    meta = run_single._load_question_metadata(qf)
    assert meta["repo"] == "pallets/flask"
    assert meta["commit"] == "abc123"


def test_resolve_target_repo_prefers_bound_repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "project"
    repo_root.mkdir()
    monkeypatch.setattr(run_single.PATH_CONFIG, "project_root", repo_root)

    called = {}

    def fake_ensure(repo_slug, commit, cache_dir):
        called["repo"] = repo_slug
        called["commit"] = commit
        called["cache_dir"] = cache_dir
        target = tmp_path / "cache" / "repo"
        target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(run_single, "_ensure_repo_checkout", fake_ensure)

    class Args:
        repo_path = None
        repo_cache_dir = None

    repo_path, info = run_single._resolve_target_repo(Args(), tmp_path / "q.txt", {"repo": "psf/requests", "commit": "deadbeef"})
    assert repo_path.endswith("repo")
    assert info["mode"] == "question_bound"
    assert called["repo"] == "psf/requests"
    assert called["commit"] == "deadbeef"
