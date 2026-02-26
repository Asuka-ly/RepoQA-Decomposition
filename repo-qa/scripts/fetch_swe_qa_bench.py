"""下载并准备 SWE-QA-Bench 数据（保留 Question-Repo-Commit 绑定）。"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List

SWE_QA_BENCH_GIT = "https://github.com/peng-weihan/SWE-QA-Bench.git"
DEFAULT_EXT_DIR = Path("data/external/SWE-QA-Bench")
DEFAULT_OUT_DIR = Path("data/questions/swe_qa_bench")
QUESTION_KEYS = (
    "question",
    "prompt",
    "query",
    "instruction",
    "problem",
    "task",
    "user_query",
)
REPO_KEYS = ("repo", "repo_name", "repository")
COMMIT_KEYS = ("commit", "base_commit", "commit_hash", "revision")
INSTANCE_KEYS = ("instance_id", "id", "qid")


def run_git_clone(url: str, target_dir: Path, refresh: bool = False) -> None:
    if target_dir.exists() and refresh:
        import shutil

        shutil.rmtree(target_dir)

    if target_dir.exists():
        return

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--depth", "1", url, str(target_dir)], check=True)


def _candidate_files(repo_dir: Path) -> List[Path]:
    files: List[Path] = []
    for p in repo_dir.rglob("*"):
        if not p.is_file():
            continue
        if any(x in p.parts for x in {".git", "node_modules", "venv", "__pycache__"}):
            continue
        if p.suffix.lower() in {".json", ".jsonl", ".csv", ".yaml", ".yml", ".md"}:
            files.append(p)
    return files


def _is_question_like(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 12 or len(t) > 1200:
        return False
    if "http://" in t or "https://" in t:
        return False
    return t.endswith("?") or t.lower().startswith(("what ", "why ", "how ", "where ", "which "))


def _pick_first_str(record: Dict[str, Any], keys: Iterable[str]) -> str | None:
    for key in keys:
        val = record.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _extract_question_text(record: Dict[str, Any]) -> str | None:
    direct = _pick_first_str(record, QUESTION_KEYS)
    if direct:
        return direct

    stack: List[Any] = list(record.values())
    while stack:
        cur = stack.pop()
        if isinstance(cur, str) and _is_question_like(cur):
            return cur.strip()
        if isinstance(cur, dict):
            nested = _pick_first_str(cur, QUESTION_KEYS)
            if nested:
                return nested
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur[:20])
    return None


def _extract_binding_metadata(record: Dict[str, Any]) -> Dict[str, Any]:
    metadata = {
        "repo": _pick_first_str(record, REPO_KEYS),
        "commit": _pick_first_str(record, COMMIT_KEYS),
        "instance_id": _pick_first_str(record, INSTANCE_KEYS),
    }
    return metadata


def _iter_json_records(path: Path) -> Iterable[Dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        with path.open(encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict):
                    yield data
        return

    with path.open(encoding="utf-8", errors="ignore") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return

    if isinstance(data, dict):
        for k in ["data", "items", "questions", "examples", "records", "instances"]:
            v = data.get(k)
            if isinstance(v, list):
                for x in v:
                    if isinstance(x, dict):
                        yield x
        yield data
    elif isinstance(data, list):
        for x in data:
            if isinstance(x, dict):
                yield x


def _iter_csv_records(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open(encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield dict(row)


def _iter_yaml_like_records(path: Path) -> Iterable[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            yield data
        elif isinstance(data, list):
            for x in data:
                if isinstance(x, dict):
                    yield x
        return
    except Exception:
        pass

    for i, line in enumerate(text.splitlines(), 1):
        clean = line.strip(" -\t#")
        if _is_question_like(clean):
            yield {"question": clean, "_line": i}


def _iter_markdown_questions(path: Path) -> Iterable[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    for i, line in enumerate(text.splitlines(), 1):
        clean = line.strip(" -\t#>*")
        if _is_question_like(clean):
            yield {"question": clean, "_line": i}


def collect_questions(repo_dir: Path, max_questions: int = 200) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    seen = set()

    for fp in _candidate_files(repo_dir):
        if len(results) >= max_questions:
            break

        suffix = fp.suffix.lower()
        if suffix in {".json", ".jsonl"}:
            iterator = _iter_json_records(fp)
        elif suffix == ".csv":
            iterator = _iter_csv_records(fp)
        elif suffix in {".yaml", ".yml"}:
            iterator = _iter_yaml_like_records(fp)
        else:
            iterator = _iter_markdown_questions(fp)

        for idx, rec in enumerate(iterator, 1):
            q = _extract_question_text(rec)
            if not q:
                continue
            q_norm = re.sub(r"\s+", " ", q).strip()
            if q_norm in seen:
                continue
            seen.add(q_norm)

            binding = _extract_binding_metadata(rec)
            results.append(
                {
                    "source_file": str(fp.relative_to(repo_dir)),
                    "source_index": idx,
                    "question": q_norm,
                    "repo": binding.get("repo"),
                    "commit": binding.get("commit"),
                    "instance_id": binding.get("instance_id"),
                }
            )
            if len(results) >= max_questions:
                break

    return results


def materialize_questions(questions: List[Dict[str, Any]], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / "index.jsonl"
    with index_path.open("w", encoding="utf-8") as idxf:
        for i, item in enumerate(questions, 1):
            qid = item.get("instance_id") or f"swe_qa_{i:04d}"
            txt_name = f"swe_qa_{i:04d}.txt"
            txt_path = output_dir / txt_name
            txt_path.write_text(item["question"].strip() + "\n", encoding="utf-8")
            row = {
                "id": qid,
                "question_file": f"swe_qa_bench/{txt_name}",
                "source_file": item.get("source_file"),
                "source_index": item.get("source_index"),
                "repo": item.get("repo"),
                "commit": item.get("commit"),
                "instance_id": item.get("instance_id"),
            }
            idxf.write(json.dumps(row, ensure_ascii=False) + "\n")
    return index_path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch and prepare SWE-QA-Bench dataset")
    p.add_argument("--repo-url", default=SWE_QA_BENCH_GIT)
    p.add_argument("--target-dir", default=str(DEFAULT_EXT_DIR))
    p.add_argument("--output-dir", default=str(DEFAULT_OUT_DIR))
    p.add_argument("--max-questions", type=int, default=200)
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--skip-clone", action="store_true", help="Use existing local target dir")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    target_dir = Path(args.target_dir)
    output_dir = Path(args.output_dir)

    if not args.skip_clone:
        run_git_clone(args.repo_url, target_dir, refresh=args.refresh)

    if not target_dir.exists():
        raise FileNotFoundError(f"Target dir not found: {target_dir}")

    questions = collect_questions(target_dir, max_questions=args.max_questions)
    if not questions:
        print("⚠️ No question-like records found. Please inspect dataset schema manually.")
        return 1

    index_path = materialize_questions(questions, output_dir)
    with_binding = sum(1 for q in questions if q.get("repo"))
    print(f"✅ Extracted questions: {len(questions)}")
    print(f"✅ Questions with repo binding: {with_binding}")
    print(f"✅ Question files dir: {output_dir}")
    print(f"✅ Index: {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
