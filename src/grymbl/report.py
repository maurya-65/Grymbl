"""`grymbl report`: a self-contained local HTML view of episodes, escalations, and cost.

The page is one file with no external resources, and its Content-Security-Policy forbids
network requests, so opening it can never send data anywhere. All text is inserted with
`textContent`; nothing from the database is ever parsed as HTML.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from importlib import resources
from pathlib import Path
from typing import Any

from grymbl.config import Settings
from grymbl.dedup import FileChange, diff_change, unapply
from grymbl.events import Event, EventKind
from grymbl.redact import redact
from grymbl.store import EpisodeRow, Store

# Per-event cap on displayed text. The database keeps everything; this only keeps the page
# responsive when a generated file produces an enormous diff.
MAX_DISPLAY_CHARS = 20_000


def build_report(
    store: Store, settings: Settings, since: datetime | None, now: datetime, days: int | None
) -> str:
    episodes = store.episodes_since(since)
    events = {episode.episode_id: store.episode_events(episode.episode_id) for episode in episodes}
    net = _net_changes(store, events)
    data = {
        "meta": {
            "repo": settings.repo_root.name,
            "developer": store.get_meta("developer") or "",
            "generated": now.isoformat(),
            "days": days,
            "dailyCap": settings.daily_call_cap,
            "model": settings.model,
            "effort": settings.effort,
        },
        "episodes": [
            _episode_json(store, episode, events[episode.episode_id], net) for episode in episodes
        ],
        "calls": [
            {
                "episode": call.episode_id,
                "ts": call.timestamp.isoformat(),
                "model": call.model,
                "inputTokens": call.input_tokens,
                "outputTokens": call.output_tokens,
                "costUsd": call.cost_usd,
            }
            for call in store.model_calls_since(since)
            if call.episode_id in events  # cost belongs to the episodes shown
        ],
    }
    template = resources.files("grymbl").joinpath("templates", "report.html")
    return template.read_text(encoding="utf-8").replace("__GRYMBL_DATA__", _embed(data))


def write_report(html: str, path: Path) -> Path:
    path.write_text(html, encoding="utf-8")
    return path


def _embed(data: dict[str, Any]) -> str:
    """JSON safe to place inside a <script> element, whatever the data contains."""
    text = json.dumps(data, ensure_ascii=False)
    return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def _net_changes(store: Store, events: dict[str, list[Event]]) -> dict[tuple[str, str], FileChange]:
    """Each episode's net change per file, keyed by (episode, path).

    Events hold only diffs, so the file as it was before and after an episode is rebuilt by
    undoing every later diff, starting from the current snapshot. A file whose history
    doesn't line up is left out, and the page shows its edits one by one instead.
    """
    owner = {
        event.event_id: episode_id
        for episode_id, episode_events in events.items()
        for event in episode_events
        if event.kind is EventKind.FILE_CHANGED
    }
    starts = [
        event.timestamp for items in events.values() for event in items if event.event_id in owner
    ]
    if not starts:
        return {}
    chains: dict[str, list[Event]] = defaultdict(list)
    for event in store.file_events_since(min(starts)):
        chains[event.files[0]].append(event)

    result: dict[tuple[str, str], FileChange] = {}
    for path, chain in chains.items():
        spans: dict[str, list[int]] = defaultdict(list)
        for index, event in enumerate(chain):
            if event.event_id in owner:
                spans[owner[event.event_id]].append(index)
        # Another episode's edit in the middle would leak into this one's net diff.
        spans = {key: idx for key, idx in spans.items() if idx[-1] - idx[0] + 1 == len(idx)}
        wanted = {i for idx in spans.values() for i in (idx[0], idx[-1] + 1)}
        snapshot = store.snapshot(path)
        text = snapshot.content if snapshot else None
        texts: dict[int, str] = {}  # the file's content just before chain[index]
        for index in range(len(chain), -1, -1):
            if text is None or not wanted:
                break
            if index in wanted:
                texts[index] = text
                wanted.discard(index)
            if index > 0:
                event = chain[index - 1]
                deleted = event.kind is EventKind.FILE_DELETED
                text = None if deleted else unapply(text, str(event.payload["diff"]))
        for episode_id, idx in spans.items():
            before, after = texts.get(idx[0]), texts.get(idx[-1] + 1)
            if before is not None and after is not None:
                result[(episode_id, path)] = diff_change(path, before, after)
    return result


def _episode_json(
    store: Store,
    episode: EpisodeRow,
    events: list[Event],
    net: dict[tuple[str, str], FileChange],
) -> dict[str, Any]:
    files = episode.files or tuple(sorted({path for event in events for path in event.files}))
    return {
        "id": episode.episode_id,
        "start": episode.timestamp_start.isoformat(),
        "end": episode.timestamp_end.isoformat(),
        "status": episode.status,
        "escalated": episode.escalated,
        "rules": list(episode.jev_rules),
        "reasons": list(episode.jev_reasons),
        "summary": episode.summary,
        "intervention": episode.intervention,
        "agent": episode.agent,
        "intent": episode.intent,
        "files": list(files),
        "changes": _changes(episode.episode_id, events, net),
        "stats": _stats(events),
        "assumptions": [
            {"statement": statement, "validity": validity}
            for statement, validity in store.assumptions_for(episode.episode_id)
        ],
        "events": [_event_json(event) for event in events if not _is_echo(event)],
    }


def _changes(
    episode_id: str, events: list[Event], net: dict[tuple[str, str], FileChange]
) -> list[dict[str, Any]]:
    """One row per file: its net diff when the history allows, otherwise every edit in turn."""
    by_path: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        if event.kind in (EventKind.FILE_CHANGED, EventKind.FILE_DELETED):
            by_path[event.files[0]].append(event)
    rows = []
    for path, edits in by_path.items():
        deleted = edits[-1].kind is EventKind.FILE_DELETED
        change = None if deleted else net.get((episode_id, path))
        if change is not None:
            added, removed, diff = change.added, change.removed, change.diff
        else:
            added = sum(int(edit.payload.get("added", 0)) for edit in edits)
            removed = sum(int(edit.payload["removed"]) for edit in edits)
            diff = "".join(str(edit.payload.get("diff", "")) for edit in edits)
        rows.append(
            {
                "path": path,
                "edits": len(edits),
                "added": added,
                "removed": removed,
                "deleted": deleted,
                "net": change is not None,
                "diff": _clip(redact(diff)),
            }
        )
    return sorted(rows, key=lambda row: -(row["added"] + row["removed"]))


def _stats(events: list[Event]) -> dict[str, Any]:
    """The counts on an episode's collapsed row."""
    commands = [event for event in events if event.kind is EventKind.COMMAND]
    tests = [event for event in events if event.kind is EventKind.TEST_RUN]
    if not tests:
        outcome = "none"
    elif tests[-1].failed:
        outcome = "failing"
    else:
        outcome = "fixed" if any(test.failed for test in tests) else "passing"
    return {
        "commands": len(commands),
        "failedCommands": sum(1 for event in commands if event.failed),
        "tests": outcome,
        "commits": sum(1 for event in events if event.kind is EventKind.COMMIT),
        "pushed": any(event.kind is EventKind.PUSH for event in events),
    }


def _is_echo(event: Event) -> bool:
    """An agent's successful file edit; the file change recorded with it says more."""
    return (
        event.kind is EventKind.AGENT_TOOL
        and "plan" not in event.payload
        and not event.payload.get("failed")
    )


def _event_json(event: Event) -> dict[str, Any]:
    title, meta, body = _describe(event)
    return {
        "kind": event.kind.value,
        "ts": event.timestamp.isoformat(),
        "title": redact(title),
        "meta": meta,
        "body": _clip(redact(body)) if body else "",
        "failed": event.failed,
        "agent": "agent" in event.payload,
    }


def _describe(event: Event) -> tuple[str, str, str]:
    """A one-line title, a short status (exit code, line counts), and an optional body."""
    payload = event.payload
    first_file = event.files[0] if event.files else ""
    match event.kind:
        case EventKind.FILE_CHANGED:
            return (
                f"Edited {first_file}",
                f"+{payload['added']} \N{MINUS SIGN}{payload['removed']}",
                str(payload["diff"]),
            )
        case EventKind.FILE_DELETED:
            return f"Deleted {first_file}", f"\N{MINUS SIGN}{payload['removed']}", ""
        case EventKind.COMMAND:
            command = str(payload["command"]).strip()
            lines = command.splitlines()
            # An agent says what each command is for, which reads better than the command.
            title = str(payload.get("description") or "") or (
                lines[0] + (" \N{HORIZONTAL ELLIPSIS}" if len(lines) > 1 else "") if lines else ""
            )
            output = str(payload.get("output_tail", "")).strip()
            return title, f"exit {payload['exit_code']}", f"$ {command}\n\n{output}".strip()
        case EventKind.COMMIT:
            message = str(payload["message"]).strip()
            subject = message.splitlines()[0] if message else ""
            return f"Commit {str(payload['sha'])[:7]}  {subject}", "", message
        case EventKind.PUSH:
            return f"Pushed to {payload['remote']}", "", "\n".join(payload["refs"])
        case EventKind.TEST_RUN:
            return (
                f"{payload['runner']}: {payload['passed']} passed, {payload['failed']} failed",
                "",
                "\n".join(f"FAILED {name}" for name in payload["failed_tests"]),
            )
        case EventKind.AGENT_PROMPT:
            prompt = str(payload["prompt"]).strip()
            first_line = prompt.splitlines()[0] if prompt else ""
            return f"Asked {payload['agent']}: {first_line}", "", prompt
        case EventKind.AGENT_TOOL if "plan" in payload:
            return f"{payload['agent']} updated its plan", "", str(payload["plan"])
        case EventKind.AGENT_TOOL:
            return f"{payload['agent']}: {payload['tool']} on {first_file} failed", "", ""
        case EventKind.AGENT_TURN_END:
            return f"{payload['agent']} replied", "claims, not evidence", str(payload["narrative"])


def _clip(text: str) -> str:
    if len(text) <= MAX_DISPLAY_CHARS:
        return text
    hidden = len(text) - MAX_DISPLAY_CHARS
    return f"{text[:MAX_DISPLAY_CHARS]}\n[... {hidden} more characters, kept in the database ...]"
