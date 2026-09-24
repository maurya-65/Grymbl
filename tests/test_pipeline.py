"""End-to-end judgment loop against a real SQLite store, with a fake analyst."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import datetime

import pytest

from grymbl.config import Settings
from grymbl.events import EventKind
from grymbl.pipeline import Pipeline
from grymbl.reasoning import AnalystResult, EpisodeAnalysis, EpisodeEvidence, Usage
from grymbl.store import Snapshot, Store
from tests.helpers import agent_event, at, change, ran_tests

# 1,000 input + 200 output tokens on Sonnet 5 = US$0.004.
FAKE_USAGE = Usage("claude-sonnet-5", 1_000, 200)


class FakeAnalyst:
    def __init__(self, intervention: str | None = None) -> None:
        self.intervention = intervention
        self.seen: list[EpisodeEvidence] = []

    def analyze(self, evidence: EpisodeEvidence) -> AnalystResult:
        self.seen.append(evidence)
        analysis = EpisodeAnalysis(
            evidence="sufficient",
            summary=f"summary of {evidence.episode_id}",
            assumptions=["auth tokens expire after 1h"],
            intervention=self.intervention,
        )
        return AnalystResult(analysis=analysis, usage=FAKE_USAGE)


class RecordingSink:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def deliver(
        self,
        episode_id: str,
        at: datetime,
        files: Sequence[str],
        reasons: Sequence[str],
        message: str,
    ) -> None:
        self.messages.append(message)


def test_routine_episode_is_recorded_without_calling_sonnet(
    store: Store, settings: Settings
) -> None:
    analyst, sink = FakeAnalyst(), RecordingSink()
    pipeline = Pipeline(store, settings, analyst, sink)
    store.add_event(change("app/auth.py", 0))
    store.add_event(change("app/auth.py", 1))

    pipeline.tick(at(2))
    [open_episode] = store.recent_episodes(5)
    assert open_episode.status == "open"

    pipeline.tick(at(20))
    [episode] = store.recent_episodes(5)
    assert episode.status == "closed"
    assert not episode.escalated
    assert episode.summary is None
    assert episode.files == ("app/auth.py",)
    assert analyst.seen == []
    assert sink.messages == []


def test_escalated_episode_gets_analysis_and_history(store: Store, settings: Settings) -> None:
    analyst, sink = FakeAnalyst(), RecordingSink()
    pipeline = Pipeline(store, settings, analyst, sink)

    store.put_snapshot("tests/test_auth.py", Snapshot("h", "from app import auth"), ["app/auth.py"])

    # First episode: fail -> retry -> pass escalates.
    store.add_event(ran_tests(0, failed=1, files=("tests/test_auth.py",)))
    store.add_event(change("app/auth.py", 1))
    store.add_event(ran_tests(2, failed=0, files=("tests/test_auth.py",)))
    pipeline.tick(at(30))

    # Second episode on the same file escalates via history and sees the first one.
    analyst.intervention = "Last time auth.py changed, token expiry broke. Check it."
    store.add_event(change("app/auth.py", 60))
    pipeline.tick(at(90))

    assert len(analyst.seen) == 2
    [prior] = analyst.seen[1].history
    assert prior.summary == f"summary of {analyst.seen[0].episode_id}"
    assert prior.assumptions == (("auth tokens expire after 1h", "unverified"),)
    assert sink.messages == ["Last time auth.py changed, token expiry broke. Check it."]


def test_escalation_without_analyst_is_still_recorded(store: Store, settings: Settings) -> None:
    pipeline = Pipeline(store, settings, None, RecordingSink())
    store.put_snapshot("api/routes.py", Snapshot("h", "from app import auth"), ["app/auth.py"])
    # Related across modules, so one episode that trips the multi-module rule.
    store.add_event(change("app/auth.py", 0))
    store.add_event(change("api/routes.py", 1))
    pipeline.tick(at(30))
    [episode] = store.recent_episodes(5)
    assert episode.escalated
    assert episode.summary is None


def test_agent_episode_records_intent_and_agent(store: Store, settings: Settings) -> None:
    analyst = FakeAnalyst()
    pipeline = Pipeline(store, settings, analyst, RecordingSink())
    store.add_event(agent_event(EventKind.AGENT_PROMPT, 0, prompt="make tokens expire"))
    store.add_event(change("app/auth.py", 1, added=0, removed=5))
    store.add_event(agent_event(EventKind.AGENT_TURN_END, 2, narrative="Only touched auth."))
    pipeline.tick(at(30))

    [episode] = store.recent_episodes(5)
    assert (episode.agent, episode.intent) == ("claude-code", "make tokens expire")
    assert episode.escalated  # deleted logic
    [evidence] = analyst.seen
    assert evidence.events[0].kind is EventKind.AGENT_PROMPT


def test_store_migrates_databases_created_before_v1_1(settings: Settings) -> None:
    settings.db_path.unlink(missing_ok=True)
    legacy = sqlite3.connect(settings.db_path)
    legacy.execute(
        "CREATE TABLE episodes (episode_id TEXT PRIMARY KEY, timestamp_start TEXT NOT NULL, "
        "timestamp_end TEXT NOT NULL, developer TEXT NOT NULL, summary TEXT, "
        "had_deletion INTEGER NOT NULL DEFAULT 0, had_fail_retry_pass INTEGER NOT NULL DEFAULT 0, "
        "escalated INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'open')"
    )
    legacy.execute(
        "INSERT INTO episodes (episode_id, timestamp_start, timestamp_end, developer) "
        "VALUES ('old', '2026-09-01T00:00:00+00:00', '2026-09-01T00:00:00+00:00', 'dev')"
    )
    legacy.commit()
    legacy.close()
    with Store(settings.db_path) as store:
        [episode] = store.recent_episodes(1)
    assert (episode.episode_id, episode.agent, episode.intent) == ("old", None, None)


def test_escalation_records_rules_warning_and_cost(store: Store, settings: Settings) -> None:
    analyst = FakeAnalyst(intervention="Check token expiry.")
    pipeline = Pipeline(store, settings, analyst, RecordingSink())
    store.add_event(change("app/auth.py", 0, added=0, removed=5))
    pipeline.tick(at(30))

    [episode] = store.recent_episodes(5)
    assert episode.jev_rules == ("deleted_logic",)
    assert episode.jev_reasons == ("deletes existing logic",)
    assert episode.intervention == "Check token expiry."
    [call] = store.model_calls_since(None)
    assert (call.episode_id, call.input_tokens, call.output_tokens) == (
        episode.episode_id,
        1_000,
        200,
    )
    assert call.cost_usd == pytest.approx(0.004)


def test_routine_episode_records_no_rules_and_no_cost(store: Store, settings: Settings) -> None:
    pipeline = Pipeline(store, settings, FakeAnalyst(), RecordingSink())
    store.add_event(change("app/auth.py", 0))
    pipeline.tick(at(30))
    [episode] = store.recent_episodes(5)
    assert (episode.jev_rules, episode.intervention) == ((), None)
    assert store.model_calls_since(None) == []
