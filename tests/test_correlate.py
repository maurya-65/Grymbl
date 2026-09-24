from __future__ import annotations

from grymbl.config import Settings
from grymbl.correlate import OpenEpisode, choose_episode, deadline, expired
from grymbl.events import EventKind
from tests.helpers import agent_event, at, change, command, ran_tests

GRAPH = {"tests/test_auth.py": frozenset({"app/auth.py"})}


def test_related_file_joins_episode_across_directories(settings: Settings) -> None:
    episode = OpenEpisode("e1", [change("app/auth.py", 0)])
    event = change("tests/test_auth.py", 1)
    assert choose_episode(event, [episode], GRAPH, settings) is episode


def test_unrelated_file_starts_new_episode(settings: Settings) -> None:
    episode = OpenEpisode("e1", [change("app/auth.py", 0)])
    assert choose_episode(change("web/page.tsx", 1), [episode], GRAPH, settings) is None


def test_commands_and_test_runs_join_the_active_episode(settings: Settings) -> None:
    episode = OpenEpisode("e1", [change("app/auth.py", 0)])
    assert choose_episode(command("ls", 1), [episode], GRAPH, settings) is episode
    assert choose_episode(ran_tests(1, 0, ("other/test_x.py",)), [episode], GRAPH, settings) is (
        episode
    )


def test_window_expires_after_idle_gap(settings: Settings) -> None:
    episode = OpenEpisode("e1", [change("app/auth.py", 0)])
    assert choose_episode(change("app/auth.py", 6), [episode], GRAPH, settings) is None
    assert expired([episode], at(6), settings) == [episode]


def test_window_extends_after_failure(settings: Settings) -> None:
    episode = OpenEpisode("e1", [change("app/auth.py", 0), ran_tests(1, failed=2)])
    assert deadline(episode, settings) == at(1) + settings.extended_gap
    assert choose_episode(change("app/auth.py", 10), [episode], GRAPH, settings) is episode
    assert expired([episode], at(10), settings) == []


def test_each_event_slides_the_window(settings: Settings) -> None:
    episode = OpenEpisode("e1", [change("app/auth.py", 0), change("app/auth.py", 4)])
    assert deadline(episode, settings) == at(4) + settings.idle_gap


def test_agent_prompt_always_opens_a_new_episode(settings: Settings) -> None:
    episode = OpenEpisode("e1", [change("app/auth.py", 0)])
    prompt = agent_event(EventKind.AGENT_PROMPT, 1, prompt="fix login")
    assert choose_episode(prompt, [episode], GRAPH, settings) is None


def test_agent_turn_collects_unrelated_file_changes(settings: Settings) -> None:
    human = OpenEpisode("human", [change("docs/notes.md", 0)])
    agent = OpenEpisode("agent", [agent_event(EventKind.AGENT_PROMPT, 1, prompt="fix login")])
    agent.events.append(change("app/auth.py", 2))
    # Unrelated to app/auth.py, but it happened during the agent's turn.
    assert choose_episode(change("web/login.ts", 3), [human, agent], GRAPH, settings) is agent


def test_agent_events_follow_their_session(settings: Settings) -> None:
    first = OpenEpisode("a", [agent_event(EventKind.AGENT_PROMPT, 0, "s1", prompt="one")])
    second = OpenEpisode("b", [agent_event(EventKind.AGENT_PROMPT, 1, "s2", prompt="two")])
    end = agent_event(EventKind.AGENT_TURN_END, 2, "s1", narrative="done")
    assert choose_episode(end, [first, second], GRAPH, settings) is first


def test_active_agent_turn_keeps_window_wide(settings: Settings) -> None:
    episode = OpenEpisode("a", [agent_event(EventKind.AGENT_PROMPT, 0, prompt="build it")])
    assert deadline(episode, settings) == at(0) + settings.extended_gap
    episode.events.append(agent_event(EventKind.AGENT_TURN_END, 1, narrative="done"))
    assert deadline(episode, settings) == at(1) + settings.idle_gap
