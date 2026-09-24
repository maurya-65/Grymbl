"""The HTML report: complete data, redacted text, and no way for content to escape."""

from __future__ import annotations

import json
import re
import sys
from typing import Any

import pytest

from grymbl.cli import main
from grymbl.config import Settings
from grymbl.events import Event, EventKind
from grymbl.pipeline import Pipeline
from grymbl.redact import REDACTED
from grymbl.report import MAX_DISPLAY_CHARS, build_report
from grymbl.store import Store
from tests.helpers import at, change
from tests.test_pipeline import FakeAnalyst, RecordingSink


def _data(html: str) -> dict[str, Any]:
    match = re.search(
        r'<script type="application/json" id="grymbl-data">(.*?)</script>', html, re.S
    )
    assert match is not None
    data: dict[str, Any] = json.loads(match.group(1))
    return data


def _escalated_episode(store: Store, settings: Settings, diff: str) -> None:
    event = Event(
        EventKind.FILE_CHANGED,
        at(0),
        "dev",
        ("app/auth.py",),
        {"diff": diff, "added": 0, "removed": 5},
    )
    store.add_event(event)
    Pipeline(store, settings, FakeAnalyst(intervention="Check expiry."), RecordingSink()).tick(
        at(30)
    )


def test_report_contains_episodes_rules_warnings_and_cost(store: Store, settings: Settings) -> None:
    _escalated_episode(store, settings, "-def check(t):\n-    return t < TTL\n")
    data = _data(build_report(store, settings, None, at(60), None))

    [episode] = data["episodes"]
    assert episode["escalated"] is True
    assert episode["rules"] == ["deleted_logic"]
    assert episode["intervention"] == "Check expiry."
    assert episode["assumptions"] == [
        {"statement": "auth tokens expire after 1h", "validity": "unverified"}
    ]
    assert episode["events"][0]["title"].startswith("Changed app/auth.py")
    [call] = data["calls"]
    assert call["costUsd"] == pytest.approx(0.004)


def test_report_redacts_and_cannot_be_broken_out_of(store: Store, settings: Settings) -> None:
    hostile = (
        "+API_KEY = 'sk-ant-api03-abcdefghijklmnopqrstuvwxyz'\n"
        "+</script><script>alert(1)</script>\n"
    )
    _escalated_episode(store, settings, hostile)
    html = build_report(store, settings, None, at(60), None)

    assert "sk-ant-api03" not in html
    assert "<script>alert(1)" not in html  # the only live </script> is the real one
    body = _data(html)["episodes"][0]["events"][0]["body"]
    assert REDACTED in body
    assert "</script><script>alert(1)</script>" in body  # preserved as inert text
    assert "Content-Security-Policy" in html


def test_huge_diffs_are_shortened_for_display(store: Store, settings: Settings) -> None:
    _escalated_episode(store, settings, "+" + "x" * (MAX_DISPLAY_CHARS + 5_000) + "\n")
    body = _data(build_report(store, settings, None, at(60), None))["episodes"][0]["events"][0][
        "body"
    ]
    assert len(body) < MAX_DISPLAY_CHARS + 200
    assert "kept in the database" in body


def test_open_episodes_show_their_files(store: Store, settings: Settings) -> None:
    store.add_event(change("app/auth.py", 0))
    Pipeline(store, settings, None, RecordingSink()).tick(at(1))  # assigned, not yet closed
    [episode] = _data(build_report(store, settings, None, at(2), None))["episodes"]
    assert (episode["status"], episode["files"]) == ("open", ["app/auth.py"])


def test_since_limits_the_range(store: Store, settings: Settings) -> None:
    _escalated_episode(store, settings, "-x = 1\n-y = 2\n-z = 3\n")
    data = _data(build_report(store, settings, at(10), at(60), 1))
    assert data["episodes"] == []
    assert data["calls"] == []


def test_report_command_writes_the_file(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with Store(settings.db_path) as store:
        store.add_event(change("app/auth.py", 0))
    monkeypatch.chdir(settings.repo_root)
    monkeypatch.setattr(sys, "argv", ["grymbl"])
    assert main(["report", "--all", "--no-open"]) == 0
    written = settings.data_dir / "report.html"
    assert written.exists()
    assert str(written) in capsys.readouterr().out
