"""Unified telemetry and decision trace export.

Owner: runtime
Boundary: telemetry/report serialization only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class UnifiedTelemetry:
    tool_calls: int = 0
    decompose_calls: int = 0
    replan_events: int = 0
    evidence_coverage: float = 0.0
    completion_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionTraceEvent:
    state: str
    action: str
    reward_proxy: float


@dataclass
class DecisionTraceExporter:
    schema_version: str = "decision_trace.v1"
    events: list[DecisionTraceEvent] = field(default_factory=list)

    def append(self, *, state: str, action: str, reward_proxy: float) -> None:
        self.events.append(DecisionTraceEvent(state=state, action=action, reward_proxy=reward_proxy))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "events": [asdict(e) for e in self.events],
        }
