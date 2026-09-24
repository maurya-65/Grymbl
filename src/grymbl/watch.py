"""The long-running watcher: file sensor + judgment loop in one process."""

from __future__ import annotations

import logging
import os
import queue
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import anthropic
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from grymbl.config import Settings, is_ignored, to_repo_path
from grymbl.events import utcnow
from grymbl.interventions import MarkdownLog
from grymbl.pipeline import Pipeline
from grymbl.reasoning import Analyst, SonnetAnalyst
from grymbl.sensors import developer_name
from grymbl.sensors.files import FileSensor
from grymbl.store import Store

log = logging.getLogger(__name__)

TICK_SECONDS = 1.0
DELETE_GRACE_SECONDS = 2.0


class _QueueingHandler(FileSystemEventHandler):
    """Runs on watchdog's thread; hands events to the main thread, which owns SQLite."""

    def __init__(self, settings: Settings, events: queue.Queue[FileSystemEvent]) -> None:
        self._settings = settings
        self._events = events

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory or event.event_type not in (
            "created",
            "modified",
            "deleted",
            "moved",
        ):
            return
        paths = [os.fsdecode(event.src_path), os.fsdecode(event.dest_path)]
        repo_paths = [to_repo_path(self._settings.repo_root, Path(p)) for p in paths if p]
        if all(p is None or is_ignored(p) for p in repo_paths):
            return
        self._events.put(event)


class AlreadyWatchingError(RuntimeError):
    pass


@contextmanager
def single_watcher(lock_path: Path) -> Iterator[None]:
    """Hold an OS-level lock so only one watcher runs per repo; freed even if we crash."""
    handle = lock_path.open("a+")
    try:
        try:
            handle.seek(0)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise AlreadyWatchingError(
                f"another watcher is already running ({lock_path})"
            ) from error
        yield
    finally:
        handle.close()


def watch(settings: Settings) -> None:
    with single_watcher(settings.data_dir / "watch.lock"), Store(settings.db_path) as store:
        developer = developer_name(store, settings.repo_root)
        sensor = FileSensor(store, settings, developer)
        log.info("Baseline synced (%d files updated)", sensor.resync())
        pipeline = Pipeline(
            store, settings, make_analyst(settings), MarkdownLog(settings.interventions_path)
        )

        router = FileEventRouter(sensor)
        events: queue.Queue[FileSystemEvent] = queue.Queue()
        observer = Observer()
        observer.schedule(
            _QueueingHandler(settings, events), str(settings.repo_root), recursive=True
        )
        observer.start()
        log.info(
            "Watching %s as %s. Silent unless something needs saying.",
            settings.repo_root,
            developer,
        )
        try:
            while True:
                _drain(events, router, time.monotonic() + TICK_SECONDS)
                pipeline.tick(utcnow())
        except KeyboardInterrupt:
            log.info("Stopping")
        finally:
            observer.stop()
            observer.join()


class FileEventRouter:
    """Feeds watchdog events to the file sensor, holding deletions briefly.

    Editors and agents often save by deleting the file and renaming a temp file into its
    place. A deletion only counts once the file has stayed gone for `grace` seconds.
    """

    def __init__(
        self,
        sensor: FileSensor,
        grace: float = DELETE_GRACE_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._sensor = sensor
        self._grace = grace
        self._clock = clock
        self._pending_deletes: dict[Path, float] = {}

    def route(self, event_type: str, source: Path, destination: Path | None = None) -> None:
        match event_type:
            case "created" | "modified":
                self._pending_deletes.pop(source, None)
                self._sensor.on_changed(source)
            case "deleted":
                self._pending_deletes[source] = self._clock()
            case "moved" if destination is not None:
                self._pending_deletes.pop(destination, None)
                self._sensor.on_moved(source, destination)

    def flush_deletes(self) -> None:
        now = self._clock()
        for path, since in list(self._pending_deletes.items()):
            if now - since >= self._grace:
                del self._pending_deletes[path]
                self._sensor.on_deleted(path)


def _drain(events: queue.Queue[FileSystemEvent], router: FileEventRouter, until: float) -> None:
    while (remaining := until - time.monotonic()) > 0:
        try:
            event = events.get(timeout=remaining)
        except queue.Empty:
            break
        destination = os.fsdecode(event.dest_path)
        router.route(
            event.event_type,
            Path(os.fsdecode(event.src_path)),
            Path(destination) if destination else None,
        )
    router.flush_deletes()


def make_analyst(settings: Settings) -> Analyst | None:
    try:
        return SonnetAnalyst(settings.model)
    except anthropic.AnthropicError as error:
        log.warning("Sonnet unavailable (%s); escalations will be recorded without analysis", error)
        return None
