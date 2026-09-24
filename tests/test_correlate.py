from __future__ import annotations

from grymbl.config import Settings
from grymbl.correlate import OpenEpisode, choose_episode, deadline, expired
from tests.helpers import at, change, command, ran_tests

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
