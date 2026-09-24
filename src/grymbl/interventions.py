"""Intervention delivery. v1 channel is a local markdown log (plan §10)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Protocol


class InterventionSink(Protocol):
    def deliver(
        self,
        episode_id: str,
        at: datetime,
        files: Sequence[str],
        reasons: Sequence[str],
        message: str,
    ) -> None: ...


class MarkdownLog:
    def __init__(self, path: Path) -> None:
        self._path = path

    def deliver(
        self,
        episode_id: str,
        at: datetime,
        files: Sequence[str],
        reasons: Sequence[str],
        message: str,
    ) -> None:
        entry = (
            f"## {at:%Y-%m-%d %H:%M} UTC - episode {episode_id}\n\n"
            f"- Files: {', '.join(files) or '(none)'}\n"
            f"- Flagged because: {'; '.join(reasons)}\n\n"
            f"{message}\n\n"
        )
        with self._path.open("a", encoding="utf-8") as log:
            log.write(entry)
        print(f"\n[grymbl] {message}\n  (episode {episode_id}, see {self._path})", flush=True)
