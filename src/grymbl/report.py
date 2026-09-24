"""`grymbl report`: a self-contained local HTML view of episodes, escalations, and cost.

The page is one file with no external resources, and its Content-Security-Policy forbids
network requests, so opening it can never send data anywhere. All text is inserted with
`textContent`; nothing from the database is ever parsed as HTML.
"""

from __future__ import annotations

import json
from datetime import datetime
from importlib import resources
from pathlib import Path
from typing import Any

from grymbl.config import Settings
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
    included = {episode.episode_id for episode in episodes}
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
        "episodes": [_episode_json(store, episode) for episode in episodes],
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
            if call.episode_id in included  # cost belongs to the episodes shown
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


def _episode_json(store: Store, episode: EpisodeRow) -> dict[str, Any]:
    events = store.episode_events(episode.episode_id)
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
        "assumptions": [
            {"statement": statement, "validity": validity}
            for statement, validity in store.assumptions_for(episode.episode_id)
        ],
        "events": [_event_json(event) for event in events],
    }


def _event_json(event: Event) -> dict[str, Any]:
    title, body = _describe(event)
    return {
        "kind": event.kind.value,
        "ts": event.timestamp.isoformat(),
        "title": redact(title),
        "body": _clip(redact(body)) if body else "",
        "failed": event.failed,
        "agent": "agent" in event.payload,
    }


def _describe(event: Event) -> tuple[str, str]:
    """A one-line title and an optional body for the timeline."""
    payload = event.payload
    first_file = event.files[0] if event.files else ""
    match event.kind:
        case EventKind.FILE_CHANGED:
            return (
                f"Changed {first_file}  (+{payload['added']} / -{payload['removed']} lines)",
                str(payload["diff"]),
            )
        case EventKind.FILE_DELETED:
            return f"Deleted {first_file}  ({payload['removed']} lines of logic)", ""
        case EventKind.COMMAND:
            who = f"{payload['agent']} ran" if "agent" in payload else "Ran"
            said = f"\n# {payload['description']}" if payload.get("description") else ""
            return (
                f"{who} $ {payload['command']}  (exit {payload['exit_code']})",
                f"{payload.get('output_tail', '')}{said}".strip(),
            )
        case EventKind.COMMIT:
            return f"Commit {str(payload['sha'])[:10]}", str(payload["message"])
        case EventKind.PUSH:
            return f"Push to {payload['remote']}", "\n".join(payload["refs"])
        case EventKind.TEST_RUN:
            return (
                f"{payload['runner']}: {payload['passed']} passed, {payload['failed']} failed",
                "\n".join(f"FAILED {name}" for name in payload["failed_tests"]),
            )
        case EventKind.AGENT_PROMPT:
            return f"Prompt to {payload['agent']} (intent)", str(payload["prompt"])
        case EventKind.AGENT_TOOL if "plan" in payload:
            return f"{payload['agent']} updated its plan", str(payload["plan"])
        case EventKind.AGENT_TOOL:
            failed = " (failed)" if payload.get("failed") else ""
            return f"{payload['agent']} used {payload['tool']} on {first_file}{failed}", ""
        case EventKind.AGENT_TURN_END:
            return f"{payload['agent']} said (claims, not evidence)", str(payload["narrative"])


def _clip(text: str) -> str:
    if len(text) <= MAX_DISPLAY_CHARS:
        return text
    hidden = len(text) - MAX_DISPLAY_CHARS
    return f"{text[:MAX_DISPLAY_CHARS]}\n[... {hidden} more characters, kept in the database ...]"
