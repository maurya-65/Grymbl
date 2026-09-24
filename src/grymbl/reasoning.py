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

Effort = Literal["low", "medium", "high"]

# Cost ceiling per call: ~25k input tokens at ~4 characters per token.
MAX_EVIDENCE_CHARS = 100_000
# Most recent prior episodes sent as history; older ones add cost, rarely judgment.
MAX_HISTORY = 10
TRIM_MARKER = "\n[... {n} characters trimmed by grymbl to cap cost ...]"

# US$ per million tokens (input, output). Each call's cost is stored when it's made, so
# history keeps the price that applied at the time even if this table changes.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-opus-5": (5.0, 25.0),
}

EVIDENCE_RULE = (
    "Only state a decision, assumption, or risk if the episode's diff, commit messages, and "
    "file history directly support it. If the evidence is thin - a change with no clear "
    'reason, no related history, no test signal explaining it - say "insufficient evidence" '
    "and record only the observed facts (what changed, where), not an inferred reason. Never "
    "fill a gap in the evidence with a plausible-sounding guess."
)

SYSTEM_PROMPT = f"""\
You are the reasoning step of a judgment layer that watches a developer's \
activity. You receive one episode (a group of related file changes, commands, test runs, \
commits) that a rule-based triage flagged, plus earlier flagged episodes on the same files.

Your job is to record what this episode established and to decide whether the developer \
should hear anything. Staying silent is a successful outcome, not a failure to act. Write \
an intervention only when this episode resembles something consequential in the provided \
history, and cite that history in the message. Otherwise leave intervention null.

Evidence rule: {EVIDENCE_RULE}

Some episodes are a coding agent's work, opened by a user prompt (the intent). What the \
agent said about its work is a claim, not evidence: never treat its explanations as \
support for a conclusion. Compare them with what the events show. A gap between what the \
agent said and what it did (e.g. "tests pass" with no passing test run, or "only touched \
the parser" with changes elsewhere) is itself an observed fact worth recording."""


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


@dataclass(frozen=True)
class Usage:
    model: str
    input_tokens: int
    output_tokens: int

    @property
    def cost_usd(self) -> float | None:
        """Cost at current list prices, or None for a model missing from the price table."""
        prices = PRICES_PER_MTOK.get(self.model)
        if prices is None:
            return None
        return (self.input_tokens * prices[0] + self.output_tokens * prices[1]) / 1_000_000


@dataclass(frozen=True)
class AnalystResult:
    """The analysis (None if the call failed or was refused) and the tokens it billed."""

    analysis: EpisodeAnalysis | None
    usage: Usage | None


NO_RESULT = AnalystResult(analysis=None, usage=None)


class Analyst(Protocol):
    def analyze(self, evidence: EpisodeEvidence) -> AnalystResult: ...


class SonnetAnalyst:
    def __init__(self, model: str, effort: Effort) -> None:
        self._model = model
        self._effort: Effort = effort
        self._client = anthropic.Anthropic()
        self._has_credentials = True

    def analyze(self, evidence: EpisodeEvidence) -> AnalystResult:
        """Ask Sonnet about one episode. Failures return no analysis and never raise."""
        if not self._has_credentials:
            return NO_RESULT
        try:
            response = self._client.messages.parse(
                model=self._model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": render_evidence(evidence)}],
                output_config={"effort": self._effort},
                output_format=EpisodeAnalysis,
            )
        except (anthropic.CredentialsError, TypeError) as error:
            # With no credentials at all, the SDK raises TypeError rather than an API error.
            if isinstance(error, TypeError) and "authentication" not in str(error):
                raise
            log.error("No Anthropic credentials; escalations are recorded without analysis")
            self._has_credentials = False
            return NO_RESULT
        except anthropic.AuthenticationError:
            log.error("Anthropic credentials missing or invalid; set ANTHROPIC_API_KEY")
            return NO_RESULT
        except anthropic.RateLimitError:
            log.warning("Rate limited analysing episode %s", evidence.episode_id)
            return NO_RESULT
        except anthropic.APIStatusError as error:
            log.warning(
                "API error %s analysing episode %s: %s",
                error.status_code,
                evidence.episode_id,
                error.message,
            )
            return NO_RESULT
        except anthropic.APIConnectionError:
            log.warning("Network error analysing episode %s", evidence.episode_id)
            return NO_RESULT

        usage = Usage(self._model, response.usage.input_tokens, response.usage.output_tokens)
        log.info(
            "Sonnet analysed episode %s: %d input, %d output tokens",
            evidence.episode_id,
            usage.input_tokens,
            usage.output_tokens,
        )
        if response.stop_reason == "refusal":
            log.warning("Model declined episode %s", evidence.episode_id)
            return AnalystResult(analysis=None, usage=usage)
        return AnalystResult(analysis=response.parsed_output, usage=usage)


def render_evidence(evidence: EpisodeEvidence, max_chars: int = MAX_EVIDENCE_CHARS) -> str:
    """Plain-text evidence for the model, capped at `max_chars` and redacted again.

    When over budget, the longest events (usually big diffs) are trimmed first, each with
    an explicit marker so the model knows the evidence is partial.
    """
    header = [
        f"<episode id={evidence.episode_id} developer={evidence.developer}>",
        f"Flagged because: {'; '.join(evidence.reasons)}",
        "",
        "<events>",
    ]
    footer = ["</events>", "</episode>", "", "<history>"]
    history = evidence.history[-MAX_HISTORY:]
    if not history:
        footer.append("No earlier flagged episodes touched these files.")
    for prior in history:
        footer.append(
            f"- episode {prior.episode_id} at {prior.timestamp_start:%Y-%m-%d %H:%M} "
            f"on {', '.join(prior.files)}"
        )
        if prior.intent:
            footer.append(f"  intent: {prior.intent}")
        footer.append(f"  summary: {prior.summary or '(no analysis recorded)'}")
        for statement, validity in prior.assumptions:
            footer.append(f"  assumption [{validity}]: {statement}")
    footer.append("</history>")

    fixed = len("\n".join(header + footer)) + len(evidence.events)
    # Redact before trimming: a cut can shorten a secret below what the patterns recognise.
    rendered = [redact(_render_event(event)) for event in evidence.events]
    events = _fit(rendered, max_chars - fixed)
    return redact("\n".join(header + events + footer))


def _fit(texts: list[str], budget: int) -> list[str]:
    """Trim the longest texts to one shared length so the total fits `budget`."""
    if sum(len(t) for t in texts) <= budget:
        return texts
    # Largest per-text cap that fits: shorter texts keep everything, longer ones share the rest.
    remaining, cap = max(budget, 0), 0
    lengths = sorted(len(t) for t in texts)
    for index, length in enumerate(lengths):
        share = remaining // (len(lengths) - index)
        if length > share:
            cap = share
            break
        remaining -= length
    return [t if len(t) <= cap else _trim(t, cap) for t in texts]


def _trim(text: str, cap: int) -> str:
    marker = TRIM_MARKER.format(n=len(text) - cap)
    return text[: max(cap - len(marker), 0)] + marker


def _render_event(event: Event) -> str:
    at = f"[{event.timestamp:%H:%M:%S}]"
    payload = event.payload
    match event.kind:
        case EventKind.FILE_CHANGED:
            return f"{at} changed {event.files[0]}\n{payload['diff']}"
        case EventKind.FILE_DELETED:
            return f"{at} deleted {event.files[0]} ({payload['removed']} lines of logic)"
        case EventKind.COMMAND if "agent" in payload:
            said = f"  # {payload['description']}" if payload["description"] else ""
            output = f"\n{payload['output_tail']}" if payload["output_tail"] else ""
            return (
                f"{at} {payload['agent']} ran $ {payload['command']}  "
                f"(exit {payload['exit_code']}){said}{output}"
            )
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
        case EventKind.AGENT_PROMPT:
            return f"{at} user prompt to {payload['agent']} (intent):\n{payload['prompt']}"
        case EventKind.AGENT_TOOL if "plan" in payload:
            return f"{at} {payload['agent']} updated its plan:\n{payload['plan']}"
        case EventKind.AGENT_TOOL:
            status = " (failed)" if payload.get("failed") else ""
            return f"{at} {payload['agent']} used {payload['tool']} on {event.files[0]}{status}"
        case EventKind.AGENT_TURN_END:
            return f"{at} {payload['agent']} said (claims, not evidence):\n{payload['narrative']}"
