"""Workflow Layer — orchestrates every component.

The workflow owns the lifecycle:
    Connection → Discovery → Configuration → Config Validation →
    Processing → Validation → Reports

UI pages only render workflow state.
UI must no longer orchestrate processing directly.

This module provides:
- WorkflowPhase enum for phase tracking
- WorkflowState for managing phase transitions
- Workflow protocol for workflow implementations
"""
from enum import IntEnum
from typing import Optional, Protocol, runtime_checkable


class WorkflowPhase(IntEnum):
    """The 7 phases of the DVA workflow."""
    CONNECTION = 0
    DISCOVERY = 1
    CONFIGURATION = 2
    CONFIG_VALIDATED = 3
    PROCESSING = 4
    VALIDATION = 5
    REPORTS = 6


PHASE_LABELS = {
    WorkflowPhase.CONNECTION: "1. Connection",
    WorkflowPhase.DISCOVERY: "2. Detection",
    WorkflowPhase.CONFIGURATION: "3. Configuration",
    WorkflowPhase.CONFIG_VALIDATED: "4. Validate Config",
    WorkflowPhase.PROCESSING: "5. Processing",
    WorkflowPhase.VALIDATION: "6. Validation",
    WorkflowPhase.REPORTS: "7. Reports",
}

PHASE_ICONS = {
    WorkflowPhase.CONNECTION: "🔌",
    WorkflowPhase.DISCOVERY: "🔍",
    WorkflowPhase.CONFIGURATION: "⚙️",
    WorkflowPhase.CONFIG_VALIDATED: "✅",
    WorkflowPhase.PROCESSING: "⚡",
    WorkflowPhase.VALIDATION: "📊",
    WorkflowPhase.REPORTS: "📄",
}


@runtime_checkable
class Workflow(Protocol):
    """Protocol that all workflows must implement."""

    @property
    def current_phase(self) -> WorkflowPhase: ...

    def advance(self) -> None: ...

    def reset(self) -> None: ...


class WorkflowState:
    """Concrete workflow state manager.

    Tracks current phase and provides advance/reset operations.
    Used by both onboarding and existing workflows.
    """

    def __init__(self, start_phase: WorkflowPhase = WorkflowPhase.CONNECTION):
        self._phase: WorkflowPhase = start_phase
        self._error: Optional[str] = None

    @property
    def current_phase(self) -> WorkflowPhase:
        return self._phase

    @current_phase.setter
    def current_phase(self, phase: WorkflowPhase):
        self._phase = phase

    @property
    def phase_label(self) -> str:
        return PHASE_LABELS.get(self._phase, "")

    @property
    def phase_icon(self) -> str:
        return PHASE_ICONS.get(self._phase, "")

    @property
    def error(self) -> Optional[str]:
        return self._error

    @error.setter
    def error(self, msg: Optional[str]):
        self._error = msg

    def advance(self) -> None:
        """Move to the next phase. Does not go past REPORTS."""
        if self._phase < WorkflowPhase.REPORTS:
            self._phase = WorkflowPhase(self._phase + 1)
            self._error = None

    def goto(self, phase: WorkflowPhase) -> None:
        """Jump to a specific phase."""
        self._phase = phase
        self._error = None

    def reset(self) -> None:
        """Reset to CONNECTION phase."""
        self._phase = WorkflowPhase.CONNECTION
        self._error = None

    def is_complete(self) -> bool:
        """True if past the REPORTS phase."""
        return self._phase > WorkflowPhase.REPORTS

    def __repr__(self) -> str:
        return f"WorkflowState(phase={self._phase.name}, label={self.phase_label!r})"
