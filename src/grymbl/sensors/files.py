"""File sensor: content-based, not save-event based (plan §2-3).

A save or rename whose content hash matches the last known state is dropped before it
ever becomes an event. Snapshots also give the "before" side of each diff.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from grymbl.config import IGNORED_DIRS, Settings, is_ignored, to_repo_path
from grymbl.dedup import content_hash, count_meaningful, diff_change
from grymbl.events import Event, EventKind, utcnow
from grymbl.imports import scan_imports
from grymbl.store import Snapshot, Store


class FileSensor:
    def __init__(self, store: Store, settings: Settings, developer: str) -> None:
        self._store = store
        self._settings = settings
        self._developer = developer

    def resync(self) -> int:
        """Silently align snapshots with the working tree; returns files updated.

        Runs on startup so edits made while the watcher was off (checkouts, pulls)
        become the new baseline instead of a flood of stale events.
        """
        current = dict(self._walk())
        known = self._store.known_files()
        updated = 0
        for path in known - current.keys():
            self._store.delete_snapshot(path)
            updated += 1
        all_files = known | current.keys()
        for path, text in current.items():
            snapshot = self._store.snapshot(path)
            if snapshot is None or snapshot.content_hash != content_hash(text):
                self._remember(path, text, all_files)
                updated += 1
        return updated

    def on_changed(self, absolute: Path) -> Event | None:
        path = self._repo_path(absolute)
        if path is None:
            return None
        text = self._read(absolute)
        if text is None:
            return None
        previous = self._store.snapshot(path)
        if previous is not None and previous.content_hash == content_hash(text):
            return None
        self._remember(path, text, self._store.known_files() | {path})
        change = diff_change(path, previous.content if previous else None, text)
        return self._record(
            EventKind.FILE_CHANGED,
            path,
            {"diff": change.diff, "added": change.added, "removed": change.removed},
        )

    def on_deleted(self, absolute: Path) -> Event | None:
        path = self._repo_path(absolute)
        if path is None:
            return None
        previous = self._store.snapshot(path)
        if previous is None:
            return None
        self._store.delete_snapshot(path)
        return self._record(
            EventKind.FILE_DELETED, path, {"removed": count_meaningful(previous.content)}
        )

    def on_moved(self, source: Path, destination: Path) -> list[Event]:
        """A rename with identical content is dropped; anything else is delete + change."""
        source_path = self._repo_path(source)
        destination_path = self._repo_path(destination)
        previous = self._store.snapshot(source_path) if source_path else None
        text = self._read(destination) if destination_path else None

        if (
            source_path
            and destination_path
            and previous
            and text is not None
            and previous.content_hash == content_hash(text)
        ):
            self._store.delete_snapshot(source_path)
            self._remember(destination_path, text, self._store.known_files())
            return []
        events = [self.on_deleted(source)] if previous else []
        events.append(self.on_changed(destination))
        return [event for event in events if event is not None]

    def _remember(self, path: str, text: str, known_files: set[str]) -> None:
        self._store.put_snapshot(
            path, Snapshot(content_hash(text), text), scan_imports(path, text, known_files)
        )

    def _record(self, kind: EventKind, path: str, payload: dict[str, Any]) -> Event:
        return self._store.add_event(Event(kind, utcnow(), self._developer, (path,), payload))

    def _repo_path(self, absolute: Path) -> str | None:
        path = to_repo_path(self._settings.repo_root, absolute)
        if path is None or path == "." or is_ignored(path):
            return None
        return path

    def _read(self, absolute: Path) -> str | None:
        """Text content, or None for missing, oversized, or binary files."""
        try:
            if absolute.stat().st_size > self._settings.max_file_bytes:
                return None
            data = absolute.read_bytes()
        except OSError:
            return None
        if b"\0" in data[:8192]:
            return None
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def _walk(self) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []
        root = self._settings.repo_root
        for directory, subdirs, names in os.walk(root):
            subdirs[:] = [d for d in subdirs if d not in IGNORED_DIRS]
            for name in names:
                absolute = Path(directory) / name
                path = self._repo_path(absolute)
                if path is not None and (text := self._read(absolute)) is not None:
                    found.append((path, text))
        return found
