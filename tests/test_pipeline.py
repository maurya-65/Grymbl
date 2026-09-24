"""End-to-end judgment loop against a real SQLite store, with a fake analyst."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from grymbl.config import Settings
from grymbl.pipeline import Pipeline
from grymbl.reasoning import EpisodeAnalysis, EpisodeEvidence
from grymbl.store import Snapshot, Store
from tests.helpers import at, change, ran_tests


class FakeAnalyst:
    def __init__(self, intervention: str | None = None) -> None:
        self.intervention = intervention
        self.seen: list[EpisodeEvidence] = []

    def analyze(self, evidence: EpisodeEvidence) -> EpisodeAnalysis | None:
        self.seen.append(evidence)
        return EpisodeAnalysis(
            evidence="sufficient",
            summary=f"summary of {evidence.episode_id}",
            assumptions=["auth tokens expire after 1h"],
            intervention=self.intervention,
        )


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
