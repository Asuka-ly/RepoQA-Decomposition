"""下载并准备 SWE-QA-Bench 数据。

用途：
1) 从 GitHub 拉取 `peng-weihan/SWE-QA-Bench` 到本地 `data/external/`；
2) 自动扫描多种结构化文件并尽可能抽取问题文本；
3) 物化成 `data/questions/swe_qa_bench/*.txt` + `index.jsonl`。

说明：
- 当前为 schema-agnostic 快速接入（优先可用性）；
- 已增强对弱结构数据（yaml/markdown）的兜底抽取，降低“0 条数据”概率。
"""
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


def run_git_clone(url: str, target_dir: Path, refresh: bool = False) -> None:
    """执行浅克隆。"""
    if target_dir.exists() and refresh:
        import shutil

        shutil.rmtree(target_dir)

    if target_dir.exists():
        return

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--depth", "1", url, str(target_dir)], check=True)


def _candidate_files(repo_dir: Path) -> List[Path]:
    """候选文件集合（放宽过滤，避免漏掉有效数据文件）。"""
    files: List[Path] = []
    for p in repo_dir.rglob("*"):
        if not p.is_file():
            continue
        if any(x in p.parts for x in {".git", "node_modules", "venv", "__pycache__"}):
            continue
        suffix = p.suffix.lower()
        if suffix in {".json", ".jsonl", ".csv", ".yaml", ".yml", ".md"}:
            files.append(p)
    return files


def _is_question_like(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 12:
        return False
    if len(t) > 1200:
        return False
    if "http://" in t or "https://" in t:
        return False
    return t.endswith("?") or t.lower().startswith(("what ", "why ", "how ", "where ", "which "))


def _extract_question_text(record: Dict[str, Any]) -> str | None:
    """优先按语义字段抽取，失败后做浅层字符串搜索。"""
    for key in QUESTION_KEYS:
        val = record.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    # fallback: nested dict/list shallow traversal
    stack: List[Any] = list(record.values())
    while stack:
        cur = stack.pop()
        if isinstance(cur, str) and _is_question_like(cur):
            return cur.strip()
        if isinstance(cur, dict):
            for key in QUESTION_KEYS:
                sub = cur.get(key)
                if isinstance(sub, str) and sub.strip():
                    return sub.strip()
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur[:20])
    return None


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
    """最小依赖 YAML 解析：优先 json 化尝试，失败则按行抽取 question-like 文本。"""
    text = path.read_text(encoding="utf-8", errors="ignore")
    # 先尝试按 JSON 解析（部分 yaml 兼容）
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

    # 行级兜底：只抓看起来像问题的行
    for i, line in enumerate(text.splitlines(), 1):
        clean = line.strip(" -\t#")
        if _is_question_like(clean):
            yield {"question": clean, "_line": i}


def _iter_markdown_questions(path: Path) -> Iterable[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    # 句子级别 question 抽取
    for i, line in enumerate(text.splitlines(), 1):
        clean = line.strip(" -\t#>*")
        if _is_question_like(clean):
            yield {"question": clean, "_line": i}


def collect_questions(repo_dir: Path, max_questions: int = 200) -> List[Dict[str, Any]]:
    """扫描并抽取可用 question。"""
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
            results.append(
                {
                    "source_file": str(fp.relative_to(repo_dir)),
                    "source_index": idx,
                    "question": q_norm,
                }
            )
            if len(results) >= max_questions:
                break

    return results


def materialize_questions(questions: List[Dict[str, Any]], output_dir: Path) -> Path:
    """把抽取结果写成 txt 问题文件和索引。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / "index.jsonl"
    with index_path.open("w", encoding="utf-8") as idxf:
        for i, item in enumerate(questions, 1):
            qid = f"swe_qa_{i:04d}"
            txt_path = output_dir / f"{qid}.txt"
            txt_path.write_text(item["question"].strip() + "\n", encoding="utf-8")
            row = {
                "id": qid,
                "question_file": txt_path.name,
                "source_file": item.get("source_file"),
                "source_index": item.get("source_index"),
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
    print(f"✅ Extracted questions: {len(questions)}")
    print(f"✅ Question files dir: {output_dir}")
    print(f"✅ Index: {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
