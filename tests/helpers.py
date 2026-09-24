"""Event builders shared by the tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from grymbl.events import Event, EventKind

T0 = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def change(path: str, minute: float, added: int = 1, removed: int = 0) -> Event:
    return Event(
        EventKind.FILE_CHANGED,
        at(minute),
        "dev",
        (path,),
        {"diff": f"--- a/{path}\n+++ b/{path}\n", "added": added, "removed": removed},
    )


def ran_tests(minute: float, failed: int, files: tuple[str, ...] = ()) -> Event:
    payload: dict[str, Any] = {
        "runner": "pytest",
        "passed": 3,
        "failed": failed,
        "failed_tests": [f"t{i}" for i in range(failed)],
    }
    return Event(EventKind.TEST_RUN, at(minute), "dev", files, payload)


def command(text: str, minute: float, exit_code: int = 0) -> Event:
    return Event(
        EventKind.COMMAND, at(minute), "dev", payload={"command": text, "exit_code": exit_code}
    )
