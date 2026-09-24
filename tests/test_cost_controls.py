"""Cost controls: evidence cap, history limit, effort setting, and daily call cap."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest

from grymbl.config import Settings
from grymbl.events import Event, EventKind
from grymbl.pipeline import Pipeline
from grymbl.reasoning import (
    MAX_HISTORY,
    EpisodeEvidence,
    SonnetAnalyst,
    render_evidence,
)
from grymbl.redact import REDACTED
from grymbl.store import PriorEpisode, Store
from tests.helpers import at, change
from tests.test_pipeline import FakeAnalyst, RecordingSink


def _diff_event(body: str) -> Event:
    return Event(
        EventKind.FILE_CHANGED, at(0), "dev", ("big.py",), {"diff": body, "added": 1, "removed": 0}
    )


def _evidence(events: list[Event], history: list[PriorEpisode] | None = None) -> EpisodeEvidence:
    return EpisodeEvidence("e1", "dev", ("deletes existing logic",), events, history or [])


def test_small_evidence_is_sent_whole() -> None:
    rendered = render_evidence(_evidence([_diff_event("+x = 1\n")]), max_chars=10_000)
    assert "+x = 1" in rendered
    assert "trimmed by grymbl" not in rendered


def test_oversized_evidence_trims_the_biggest_event_and_says_so() -> None:
    events = [_diff_event("+small\n"), _diff_event("+" + "y" * 50_000)]
    rendered = render_evidence(_evidence(events), max_chars=5_000)
    assert len(rendered) <= 5_000
    assert "+small" in rendered  # short events survive intact
    assert "characters trimmed by grymbl to cap cost" in rendered


def test_trimming_never_leaves_a_partial_secret() -> None:
    secret = "sk-ant-api03-" + "a" * 40
    body = "+" + "z" * 3_000 + f"\n+KEY = '{secret}'\n" + "+" + "z" * 3_000
    evidence = _evidence([_diff_event(body)])
    # Sweep the cut across the secret: no size may leave any recognisable piece of it.
    for max_chars in range(2_900, 3_400, 7):
        rendered = render_evidence(evidence, max_chars=max_chars)
        assert "sk-" not in rendered, max_chars
    assert REDACTED in render_evidence(evidence, max_chars=10_000)


def test_history_is_limited_to_recent_episodes() -> None:
    history = [
        PriorEpisode(f"old{i}", datetime(2026, 9, 1), ("a.py",), None, f"summary {i}", ())
        for i in range(MAX_HISTORY + 5)
    ]
    rendered = render_evidence(_evidence([_diff_event("+x\n")], history))
    assert "summary 0\n" not in rendered
    assert f"summary {MAX_HISTORY + 4}" in rendered


def test_effort_is_sent_with_each_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    analyst = SonnetAnalyst("claude-sonnet-5", "medium")
    sent: dict[str, Any] = {}

    def fake_parse(**kwargs: Any) -> Any:
        sent.update(kwargs)
        usage = SimpleNamespace(input_tokens=1, output_tokens=1)
        return SimpleNamespace(usage=usage, stop_reason="end_turn", parsed_output=None)

    monkeypatch.setattr(analyst._client.messages, "parse", fake_parse)
    analyst.analyze(_evidence([_diff_event("+x\n")]))
    assert sent["output_config"] == {"effort": "medium"}
    assert sent["model"] == "claude-sonnet-5"


def test_daily_cap_stops_calls_but_still_records_escalations(
    store: Store, settings: Settings
) -> None:
    analyst = FakeAnalyst()
    pipeline = Pipeline(store, replace(settings, daily_call_cap=1), analyst, RecordingSink())
    for minute in (0, 30):  # two separate escalating episodes on the same day
        store.add_event(change("app/auth.py", minute, added=0, removed=5))
        pipeline.tick(at(minute + 20))

    assert len(analyst.seen) == 1
    episodes = store.recent_episodes(5)
    assert [e.escalated for e in episodes] == [True, True]
    assert store.calls_on(f"{at(0):%Y-%m-%d}") == 1
