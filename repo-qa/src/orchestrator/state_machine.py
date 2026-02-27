"""Thin orchestrator state machine.

Owner: orchestrator
Boundary: state transitions only.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OrchestratorState:
    name: str = "init"


class Stage1Orchestrator:
    def __init__(self):
        self.state = OrchestratorState()

    def transition(self, event: str) -> str:
        if self.state.name == "init" and event == "plan_ready":
            self.state.name = "executing"
        elif self.state.name == "executing" and event == "replan":
            self.state.name = "replanning"
        elif self.state.name == "replanning" and event == "plan_ready":
            self.state.name = "executing"
        elif event == "complete":
            self.state.name = "completed"
        return self.state.name
