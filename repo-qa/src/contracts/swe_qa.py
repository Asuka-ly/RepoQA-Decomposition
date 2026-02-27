"""SWE-QA data contract and adapter.

Owner: data-platform
Boundary: only dataset parsing/validation; no agent/runtime logic.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

QUESTION_KEYS = (
    "question",
    "question_text",
    "question_body",
    "prompt",
    "query",
    "problem_statement",
    "instruction",
    "problem",
    "task",
    "user_query",
)
REPO_KEYS = ("repo", "repo_name", "repository", "repo_path", "repo_full_name")
COMMIT_KEYS = ("commit", "base_commit", "commit_hash", "revision", "sha")
INSTANCE_KEYS = ("instance_id", "id", "qid")

REASON_MISSING_QUESTION = "missing_question"
REASON_MISSING_REPO = "missing_repo"
REASON_MISSING_COMMIT = "missing_commit"
REASON_INVALID_QUESTION = "invalid_question"


@dataclass(frozen=True)
class SWEQARecord:
    """Strict SWE-QA runtime record."""

    question: str
    repo: str
    commit: str
    instance_id: str
    schema_version: str = "swe_qa_record.v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InvalidSWEQARecord:
    """Invalid sample with reason code for observability."""

    reason_code: str
    raw_preview: str


def _pick_first_str(record: dict[str, Any], keys: Iterable[str]) -> str | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _pick_nested_first_str(record: dict[str, Any], keys: Iterable[str], max_nodes: int = 200) -> str | None:
    direct = _pick_first_str(record, keys)
    if direct:
        return direct

    stack: list[Any] = [record]
    seen = 0
    while stack and seen < max_nodes:
        cur = stack.pop()
        seen += 1
        if isinstance(cur, dict):
            nested = _pick_first_str(cur, keys)
            if nested:
                return nested
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur[:30])
    return None


class SWEQAAdapter:
    """Converts raw dataset row into strict SWEQARecord."""

    def adapt(self, raw: dict[str, Any]) -> SWEQARecord | InvalidSWEQARecord:
        question = _pick_nested_first_str(raw, QUESTION_KEYS)
        if not question:
            return InvalidSWEQARecord(REASON_MISSING_QUESTION, str(raw)[:200])

        question = " ".join(question.split())
        if question.startswith("#") or question.startswith("```") or len(question) < 12:
            return InvalidSWEQARecord(REASON_INVALID_QUESTION, question[:200])

        repo = _pick_nested_first_str(raw, REPO_KEYS)
        if not repo:
            return InvalidSWEQARecord(REASON_MISSING_REPO, question[:200])

        commit = _pick_nested_first_str(raw, COMMIT_KEYS)
        if not commit:
            return InvalidSWEQARecord(REASON_MISSING_COMMIT, question[:200])

        instance_id = _pick_nested_first_str(raw, INSTANCE_KEYS) or ""
        return SWEQARecord(
            question=question,
            repo=repo,
            commit=commit,
            instance_id=instance_id,
        )
