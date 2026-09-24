"""Sonnet deep reasoning for escalated episodes, bound by the evidence rule (plan §11)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

import anthropic
from pydantic import BaseModel, Field

from grymbl.events import Event, EventKind
from grymbl.redact import redact
from grymbl.store import PriorEpisode

log = logging.getLogger(__name__)

EVIDENCE_RULE = (
    "Only state a decision, assumption, or risk if the episode's diff, commit messages, and "
    "file history directly support it. If the evidence is thin - a change with no clear "
    'reason, no related history, no test signal explaining it - say "insufficient evidence" '
    "and record only the observed facts (what changed, where), not an inferred reason. Never "
    "fill a gap in the evidence with a plausible-sounding guess."
)

SYSTEM_PROMPT = f"""\
You are the reasoning step of a judgment layer that watches a small team's development \
activity. You receive one episode (a group of related file changes, commands, test runs, \
commits) that a rule-based triage flagged, plus earlier flagged episodes on the same files.

Your job is to record what this episode established and to decide whether the developer \
should hear anything. Staying silent is a successful outcome, not a failure to act. Write \
an intervention only when this episode resembles something consequential in the provided \
history, and cite that history in the message. Otherwise leave intervention null.

Evidence rule: {EVIDENCE_RULE}"""


class EpisodeAnalysis(BaseModel):
    evidence: Literal["sufficient", "insufficient"]
    summary: str = Field(
        description="Observed facts: what changed and where. Reasons only if directly supported."
    )
    assumptions: list[str] = Field(
        description="Decisions or assumptions the evidence directly supports. Empty if none."
    )
    intervention: str | None = Field(
        description="Short evidence-backed message to the developer, or null to stay silent."
    )


@dataclass(frozen=True)
class EpisodeEvidence:
    episode_id: str
    developer: str
    reasons: tuple[str, ...]
    events: Sequence[Event]
    history: Sequence[PriorEpisode]


class Analyst(Protocol):
    def analyze(self, evidence: EpisodeEvidence) -> EpisodeAnalysis | None: ...


class SonnetAnalyst:
    def __init__(self, model: str) -> None:
        self._model = model
        self._client = anthropic.Anthropic()

    def analyze(self, evidence: EpisodeEvidence) -> EpisodeAnalysis | None:
        """Ask Sonnet about one episode; None if the call fails or is refused."""
        try:
            response = self._client.messages.parse(
                model=self._model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": render_evidence(evidence)}],
                output_format=EpisodeAnalysis,
            )
        except anthropic.AuthenticationError:
            log.error("Anthropic credentials missing or invalid; set ANTHROPIC_API_KEY")
            return None
        except anthropic.RateLimitError:
            log.warning("Rate limited analysing episode %s", evidence.episode_id)
            return None
        except anthropic.APIStatusError as error:
            log.warning("API error %s analysing episode %s", error.status_code, evidence.episode_id)
            return None
        except anthropic.APIConnectionError:
            log.warning("Network error analysing episode %s", evidence.episode_id)
            return None

        if response.stop_reason == "refusal":
            log.warning("Model declined episode %s", evidence.episode_id)
            return None
        return response.parsed_output


def render_evidence(evidence: EpisodeEvidence) -> str:
    """Plain-text evidence for the model. Everything passes through redaction again."""
    lines = [
        f"<episode id={evidence.episode_id} developer={evidence.developer}>",
        f"Flagged because: {'; '.join(evidence.reasons)}",
        "",
        "<events>",
    ]
    for event in evidence.events:
        lines.append(_render_event(event))
    lines += ["</events>", "</episode>", "", "<history>"]
    if not evidence.history:
        lines.append("No earlier flagged episodes touched these files.")
    for prior in evidence.history:
        lines.append(
            f"- episode {prior.episode_id} at {prior.timestamp_start:%Y-%m-%d %H:%M} "
            f"on {', '.join(prior.files)}"
        )
        lines.append(f"  summary: {prior.summary or '(no analysis recorded)'}")
        for statement, validity in prior.assumptions:
            lines.append(f"  assumption [{validity}]: {statement}")
    lines.append("</history>")
    return redact("\n".join(lines))


def _render_event(event: Event) -> str:
    at = f"[{event.timestamp:%H:%M:%S}]"
    payload = event.payload
    match event.kind:
        case EventKind.FILE_CHANGED:
            return f"{at} changed {event.files[0]}\n{payload['diff']}"
        case EventKind.FILE_DELETED:
            return f"{at} deleted {event.files[0]} ({payload['removed']} lines of logic)"
        case EventKind.COMMAND:
            return f"{at} $ {payload['command']}  (exit {payload['exit_code']})"
        case EventKind.COMMIT:
            files = ", ".join(event.files)
            return f"{at} commit {payload['sha'][:10]} on {files}\n{payload['message']}"
        case EventKind.PUSH:
            return f"{at} push to {payload['remote']}: {', '.join(payload['refs'])}"
        case EventKind.TEST_RUN:
            failures = "".join(f"\n  FAILED {name}" for name in payload["failed_tests"])
            return (
                f"{at} {payload['runner']} run: {payload['passed']} passed, "
                f"{payload['failed']} failed{failures}"
            )
