"""Sub-question 状态管理器

为后续 RL 训练提供结构化、可更新的中间状态：
- 每轮 observation 触发状态更新
- 记录可学习的 transition 轨迹
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any
import re


@dataclass
class SubQuestionTransition:
    step: int
    subq_id: str
    status_before: str
    status_after: str
    progress_before: float
    progress_after: float
    signal: str


@dataclass
class SubQuestionManager:
    sub_questions: List[Dict[str, Any]] = field(default_factory=list)
    transitions: List[SubQuestionTransition] = field(default_factory=list)
    replan_events: List[Dict[str, Any]] = field(default_factory=list)
    no_new_evidence_steps: int = 0
    _last_total_evidence: int = 0
    quality_history: List[Dict[str, Any]] = field(default_factory=list)

    def initialize(self, decomposition: Dict[str, Any]):
        self.sub_questions = [dict(x) for x in decomposition.get("sub_questions", [])]
        self.transitions = []
        self.replan_events = []
        self.no_new_evidence_steps = 0
        self._last_total_evidence = 0
        self.quality_history = []

    def update(self, step: int, action: str, observation: str, graph_hint: str = ""):
        """根据 action/observation 轻量更新 sub-question 状态。"""
        if not self.sub_questions:
            return

        signal = f"action={action[:80]}"
        combined_text = f"{action}\n{observation}\n{graph_hint}".lower()

        for sq in self.sub_questions:
            before_status = sq.get("status", "open")
            before_progress = float(sq.get("progress", 0.0))

            required = [x.lower() for x in sq.get("required_evidence", [])]
            hit_score = 0.0
            evidence_found = sq.setdefault("evidence_found", [])

            symbol_hits = 0
            for symbol in sq.get("symbols", []):
                if symbol.lower() in combined_text:
                    symbol_hits += 1
                    hit_score += 0.2

            required_hits = 0
            for req in required:
                tokens = [
                    t for t in re.findall(r"[a-z_]{3,}", req)
                    if t not in {"the", "for", "with", "from", "and"}
                ]
                if tokens and any(t in combined_text for t in tokens):
                    required_hits += 1
                    hit_score += 0.2

            entry_hits = 0
            for entry in sq.get("entry_candidates", []):
                if isinstance(entry, str) and entry.lower() in combined_text:
                    entry_hits += 1
                    hit_score += 0.15

            is_targeted = (symbol_hits + required_hits + entry_hits) > 0

            refs = re.findall(r"\b[\w/.-]+\.py:\d+\b", observation)
            if refs and is_targeted:
                hit_score += 0.35
                for ref in refs:
                    if ref not in evidence_found:
                        evidence_found.append(ref)

            if is_targeted and ".py" in action and re.search(r"^\s*\d+\s+", observation, re.MULTILINE):
                hit_score += 0.2
                file_match = re.search(r"([\w/.-]+\.py)", action)
                pseudo_ref = f"{file_match.group(1)}:nl" if file_match else "unknown.py:nl"
                if pseudo_ref not in evidence_found:
                    evidence_found.append(pseudo_ref)

            if is_targeted and re.search(r"^\s*\d+:", observation, re.MULTILINE) and ".py" in action:
                hit_score += 0.2
                file_match = re.search(r"([\w/.-]+\.py)", action)
                line_match = re.search(r"^\s*(\d+):", observation, re.MULTILINE)
                if file_match and line_match:
                    rg_ref = f"{file_match.group(1)}:{line_match.group(1)}"
                    if rg_ref not in evidence_found:
                        evidence_found.append(rg_ref)

            if is_targeted and "[graph hint]" in graph_hint.lower():
                hit_score += 0.2

            new_progress = min(1.0, before_progress + hit_score)
            sq["progress"] = round(new_progress, 3)
            sq["attempts"] = int(sq.get("attempts", 0)) + 1

            targeted_hits = symbol_hits + required_hits + entry_hits

            if len(evidence_found) >= 2 and new_progress >= 0.65 and targeted_hits >= 2:
                sq["status"] = "satisfied"
            elif len(evidence_found) >= 3 and new_progress >= 0.45 and targeted_hits >= 1:
                sq["status"] = "satisfied"
            elif new_progress >= 1.0 and len(evidence_found) >= 1 and targeted_hits >= 1:
                sq["status"] = "satisfied"
            elif hit_score > 0:
                sq["status"] = "in_progress"
            elif sq["attempts"] >= 5 and new_progress < 0.3:
                sq["status"] = "blocked"
            else:
                sq["status"] = before_status or "open"

            signal = (
                f"action={action[:70]} | symbol_hits={symbol_hits} | required_hits={required_hits} "
                f"| entry_hits={entry_hits} | refs_added={len(evidence_found)} | hit_score={round(hit_score, 3)}"
            )

            self.transitions.append(
                SubQuestionTransition(
                    step=step,
                    subq_id=sq.get("id", "unknown"),
                    status_before=before_status,
                    status_after=sq.get("status", "open"),
                    progress_before=before_progress,
                    progress_after=sq.get("progress", 0.0),
                    signal=signal,
                )
            )

        self._update_live_quality(step)

    def _update_live_quality(self, step: int):
        total = len(self.sub_questions) if self.sub_questions else 1
        satisfied = sum(1 for sq in self.sub_questions if sq.get("status") == "satisfied")
        progress_avg = sum(float(sq.get("progress", 0.0)) for sq in self.sub_questions) / total

        total_evidence = sum(len(sq.get("evidence_found", [])) for sq in self.sub_questions)
        evidence_delta = max(0, total_evidence - self._last_total_evidence)
        if evidence_delta == 0:
            self.no_new_evidence_steps += 1
        else:
            self.no_new_evidence_steps = 0
        self._last_total_evidence = total_evidence

        evidence_yield = min(1.0, total_evidence / max(1, total * 2))
        score = round(0.5 * (satisfied / total) + 0.3 * progress_avg + 0.2 * evidence_yield, 4)
        self.quality_history.append(
            {
                "step": step,
                "score": score,
                "completion_rate": round(satisfied / total, 4),
                "progress_avg": round(progress_avg, 4),
                "evidence_yield": round(evidence_yield, 4),
                "evidence_delta": evidence_delta,
            }
        )

    def snapshot(self) -> Dict[str, Any]:
        return {
            "sub_questions": self.sub_questions,
            "transitions": [
                {
                    "step": t.step,
                    "subq_id": t.subq_id,
                    "status_before": t.status_before,
                    "status_after": t.status_after,
                    "progress_before": t.progress_before,
                    "progress_after": t.progress_after,
                    "signal": t.signal,
                }
                for t in self.transitions
            ],
            "replan_events": self.replan_events,
            "quality_history": self.quality_history,
            "no_new_evidence_steps": self.no_new_evidence_steps,
        }

    def check_replan_needed(self, step: int) -> bool:
        """质量触发 + blocked 触发的重规划信号。"""
        reasons = []
        blocked_ids = [sq.get("id", "unknown") for sq in self.sub_questions if sq.get("status") == "blocked"]
        if blocked_ids:
            reasons.append("blocked_sub_questions_detected")

        if self.no_new_evidence_steps >= 3:
            reasons.append("no_new_evidence_for_3_steps")

        stagnant_high_priority = [
            sq.get("id", "unknown")
            for sq in self.sub_questions
            if int(sq.get("priority", 99)) <= 2
            and float(sq.get("progress", 0.0)) < 0.35
            and int(sq.get("attempts", 0)) >= 3
            and sq.get("status") != "satisfied"
        ]
        if stagnant_high_priority:
            reasons.append("high_priority_stagnation")

        if len(self.quality_history) >= 2:
            prev = self.quality_history[-2]["score"]
            cur = self.quality_history[-1]["score"]
            if cur < prev - 0.15:
                reasons.append("decomposition_quality_drop")

        if not reasons:
            return False

        event = {
            "step": step,
            "reasons": reasons,
            "blocked_sub_questions": blocked_ids,
            "stagnant_high_priority": stagnant_high_priority,
            "no_new_evidence_steps": self.no_new_evidence_steps,
            "quality_score": self.quality_history[-1]["score"] if self.quality_history else None,
        }
        if not self.replan_events or self.replan_events[-1].get("step") != step:
            self.replan_events.append(event)
        return True
