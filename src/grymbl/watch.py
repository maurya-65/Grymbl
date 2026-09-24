"""The long-running watcher: file sensor + judgment loop in one process."""

from __future__ import annotations

import logging
import os
import queue
import time
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


def watch(settings: Settings) -> None:
    with Store(settings.db_path) as store:
        developer = developer_name(store, settings.repo_root)
        sensor = FileSensor(store, settings, developer)
        log.info("Baseline synced (%d files updated)", sensor.resync())
        pipeline = Pipeline(
            store, settings, _make_analyst(settings), MarkdownLog(settings.interventions_path)
        )

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
                _drain(events, sensor, time.monotonic() + TICK_SECONDS)
                pipeline.tick(utcnow())
        except KeyboardInterrupt:
            log.info("Stopping")
        finally:
            observer.stop()
            observer.join()


def _drain(events: queue.Queue[FileSystemEvent], sensor: FileSensor, until: float) -> None:
    while (remaining := until - time.monotonic()) > 0:
        try:
            event = events.get(timeout=remaining)
        except queue.Empty:
            return
        source = Path(os.fsdecode(event.src_path))
        match event.event_type:
            case "created" | "modified":
                sensor.on_changed(source)
            case "deleted":
                sensor.on_deleted(source)
            case "moved":
                sensor.on_moved(source, Path(os.fsdecode(event.dest_path)))


def _make_analyst(settings: Settings) -> Analyst | None:
    try:
        return SonnetAnalyst(settings.model)
    except anthropic.AnthropicError as error:
        log.warning("Sonnet unavailable (%s); escalations will be recorded without analysis", error)
        return None
