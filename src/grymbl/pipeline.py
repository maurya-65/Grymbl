"""One tick of the judgment loop: correlate new events, close quiet episodes, triage."""

from __future__ import annotations

import logging
from datetime import datetime

from grymbl.config import Settings
from grymbl.correlate import OpenEpisode, choose_episode, expired
from grymbl.interventions import InterventionSink
from grymbl.jev import Triage, triage
from grymbl.reasoning import Analyst, EpisodeAnalysis, EpisodeEvidence
from grymbl.store import ClosedEpisode, ModelCall, Store, new_episode_id

log = logging.getLogger(__name__)


class Pipeline:
    def __init__(
        self, store: Store, settings: Settings, analyst: Analyst | None, sink: InterventionSink
    ) -> None:
        self._store = store
        self._settings = settings
        self._analyst = analyst
        self._sink = sink

    def tick(self, now: datetime) -> None:
        episodes = [
            OpenEpisode(episode_id, self._store.episode_events(episode_id))
            for episode_id in self._store.open_episode_ids()
        ]
        graph = self._store.import_graph()
        for event in self._store.unassigned_events():
            episode = choose_episode(event, episodes, graph, self._settings)
            if episode is None:
                episode = OpenEpisode(new_episode_id())
                episodes.append(episode)
            self._store.attach_event(episode.episode_id, event)
            episode.events.append(event)

        for episode in expired(episodes, now, self._settings):
            self._close(episode, now)

    def _close(self, episode: OpenEpisode, now: datetime) -> None:
        files = tuple(sorted(episode.files))
        decision = triage(
            episode.events,
            self._store.escalated_files(excluding_episode=episode.episode_id),
            self._settings.deletion_threshold,
        )
        analysis = self._analyze(episode, decision, files, now) if decision.escalate else None
        intervention = analysis.intervention if analysis is not None else None
        if intervention:
            self._sink.deliver(episode.episode_id, now, files, decision.reasons, intervention)

        self._store.close_episode(
            ClosedEpisode(
                episode_id=episode.episode_id,
                summary=analysis.summary if analysis is not None else None,
                had_deletion=decision.had_deletion,
                had_fail_retry_pass=decision.had_fail_retry_pass,
                escalated=decision.escalate,
                files=files,
                agent=episode.agent,
                intent=episode.intent,
                jev_rules=decision.rules,
                jev_reasons=decision.reasons,
                intervention=intervention or None,
            )
        )
        if analysis is not None and analysis.assumptions:
            self._store.add_assumptions(episode.episode_id, analysis.assumptions)

    def _analyze(
        self, episode: OpenEpisode, decision: Triage, files: tuple[str, ...], now: datetime
    ) -> EpisodeAnalysis | None:
        log.info("Escalating episode %s: %s", episode.episode_id, "; ".join(decision.reasons))
        if self._analyst is None:
            return None
        day = f"{now:%Y-%m-%d}"
        if self._store.calls_on(day) >= self._settings.daily_call_cap:
            log.warning(
                "Daily cap of %d Sonnet calls reached; recording episode %s without analysis",
                self._settings.daily_call_cap,
                episode.episode_id,
            )
            return None
        self._store.count_call(day)
        result = self._analyst.analyze(
            EpisodeEvidence(
                episode_id=episode.episode_id,
                developer=episode.developer,
                reasons=decision.reasons,
                events=episode.events,
                history=self._store.history_for(files, episode.episode_id),
            )
        )
        if result.usage is not None:
            self._store.record_model_call(
                ModelCall(
                    episode_id=episode.episode_id,
                    timestamp=now,
                    model=result.usage.model,
                    input_tokens=result.usage.input_tokens,
                    output_tokens=result.usage.output_tokens,
                    cost_usd=result.usage.cost_usd,
                )
            )
        return result.analysis
