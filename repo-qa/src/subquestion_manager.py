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

    def initialize(self, decomposition: Dict[str, Any]):
        self.sub_questions = [dict(x) for x in decomposition.get("sub_questions", [])]
        self.transitions = []
        self.replan_events = []

    def update(self, step: int, action: str, observation: str, graph_hint: str = ""):
        """根据 action/observation 轻量更新 sub-question 状态。"""
        if not self.sub_questions:
            return

        signal = f"action={action[:80]}"
        for sq in self.sub_questions:
            before_status = sq.get("status", "open")
            before_progress = float(sq.get("progress", 0.0))

            required = [x.lower() for x in sq.get("required_evidence", [])]
            hit_score = 0.0

            combined_text = f"{action}\n{observation}\n{graph_hint}".lower()
            for req in required:
                # 关键词命中可作为弱证据
                key = req.split()[0] if req else ""
                if key and key in combined_text:
                    hit_score += 0.25

            for symbol in sq.get("symbols", []):
                if symbol.lower() in combined_text:
                    hit_score += 0.2

            # 行号/文件命中代表更强证据
            if re.search(r"\b\w+\.py:\d+\b", observation):
                hit_score += 0.35

            # 图提示命中
            if "[graph hint]" in graph_hint.lower():
                hit_score += 0.2

            new_progress = min(1.0, before_progress + hit_score)
            sq["progress"] = round(new_progress, 3)
            sq["attempts"] = int(sq.get("attempts", 0)) + 1

            if new_progress >= 1.0:
                sq["status"] = "satisfied"
            elif hit_score > 0:
                sq["status"] = "in_progress"
            elif sq["attempts"] >= 4 and new_progress < 0.35:
                sq["status"] = "blocked"
            else:
                sq["status"] = before_status or "open"

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
        }

    def check_replan_needed(self, step: int) -> bool:
        """当出现 blocked 子问题时触发重规划信号（最小可用版）。"""
        blocked_ids = [sq.get("id", "unknown") for sq in self.sub_questions if sq.get("status") == "blocked"]
        if not blocked_ids:
            return False
        event = {
            "step": step,
            "blocked_sub_questions": blocked_ids,
            "reason": "blocked_sub_questions_detected",
        }
        # 避免同一步重复记事件
        if not self.replan_events or self.replan_events[-1].get("step") != step:
            self.replan_events.append(event)
        return True
