"""Episode correlation: adaptive time window + file overlap by dependency (plan §4).

Agent work (v1.1) has a firmer boundary: each prompt opens an episode, and everything the
agent does in that session, plus any file change during its turn, belongs to it.

Pure logic over in-memory episodes; the pipeline handles persistence.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from grymbl.config import Settings
from grymbl.events import Event, EventKind
from grymbl.imports import ImportGraph, related

# Events that describe what the developer is doing now rather than which code changed,
# so they join the active episode even without a file relation.
_CONTEXT_KINDS = frozenset({EventKind.COMMAND, EventKind.TEST_RUN, EventKind.PUSH})
_FILE_KINDS = frozenset({EventKind.FILE_CHANGED, EventKind.FILE_DELETED})


@dataclass
class OpenEpisode:
    episode_id: str
    events: list[Event] = field(default_factory=list)

    @property
    def developer(self) -> str:
        return self.events[0].developer

    @property
    def files(self) -> set[str]:
        return {path for event in self.events for path in event.files}

    @property
    def last_activity(self) -> datetime:
        return self.events[-1].timestamp

    @property
    def agent_session(self) -> str | None:
        """Session id of the agent prompt that opened this episode, if any."""
        for event in self.events:
            if event.kind is EventKind.AGENT_PROMPT:
                return str(event.payload["session_id"])
        return None

    @property
    def agent(self) -> str | None:
        return next((str(e.payload["agent"]) for e in self.events if "agent" in e.payload), None)

    @property
    def intent(self) -> str | None:
        """The prompt that opened this episode, already redacted."""
        for event in self.events:
            if event.kind is EventKind.AGENT_PROMPT:
                return str(event.payload["prompt"])
        return None

    @property
    def agent_turn_active(self) -> bool:
        return self.agent_session is not None and not any(
            event.kind is EventKind.AGENT_TURN_END for event in self.events
        )


def deadline(episode: OpenEpisode, settings: Settings) -> datetime:
    """When the episode closes if nothing else happens.

    Every related event slides the window forward. A failure widens it because the
    developer is usually still reading output, and so does an agent turn in progress,
    because a long build or test run can sit between two tool calls.
    """
    last = episode.events[-1]
    wide = last.failed or episode.agent_turn_active
    gap = settings.extended_gap if wide else settings.idle_gap
    return last.timestamp + gap


def choose_episode(
    event: Event,
    episodes: Sequence[OpenEpisode],
    graph: ImportGraph,
    settings: Settings,
) -> OpenEpisode | None:
    """The open episode `event` belongs to, or None if it starts a new one."""
    active = sorted(
        (
            ep
            for ep in episodes
            if ep.events
            and ep.developer == event.developer
            and event.timestamp <= deadline(ep, settings)
        ),
        key=lambda ep: ep.last_activity,
        reverse=True,
    )
    if not active or event.kind is EventKind.AGENT_PROMPT:
        return None
    if session := event.payload.get("session_id"):
        for episode in active:
            if episode.agent_session == session:
                return episode
    if event.kind in _FILE_KINDS:
        for episode in active:
            if episode.agent_turn_active:
                return episode
    if not event.files:
        return active[0]
    for episode in active:
        episode_files = episode.files
        if not episode_files or any(
            related(a, b, graph) for a in event.files for b in episode_files
        ):
            return episode
    return active[0] if event.kind in _CONTEXT_KINDS else None


def expired(
    episodes: Sequence[OpenEpisode], now: datetime, settings: Settings
) -> list[OpenEpisode]:
    return [ep for ep in episodes if ep.events and now > deadline(ep, settings)]
