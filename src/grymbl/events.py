"""Normalized sensor events: the only shape the rest of the system sees."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class EventKind(StrEnum):
    FILE_CHANGED = "file_changed"
    FILE_DELETED = "file_deleted"
    COMMAND = "command"
    COMMIT = "commit"
    PUSH = "push"
    TEST_RUN = "test_run"
    # Coding-agent activity (v1.1). Agent shell commands are recorded as COMMAND.
    AGENT_PROMPT = "agent_prompt"
    AGENT_TOOL = "agent_tool"
    AGENT_TURN_END = "agent_turn_end"


@dataclass(frozen=True)
class Event:
    kind: EventKind
    timestamp: datetime
    developer: str
    files: tuple[str, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: int | None = None

    @property
    def failed(self) -> bool:
        """True for a failing test run or a command that exited non-zero."""
        if self.kind is EventKind.TEST_RUN:
            return int(self.payload["failed"]) > 0
        if self.kind is EventKind.COMMAND:
            return int(self.payload["exit_code"]) != 0
        return False


def utcnow() -> datetime:
    return datetime.now(UTC)
