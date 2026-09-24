"""The hook entry points: redaction before storage, and never failing loudly."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

from grymbl.cli import main
from grymbl.config import Settings
from grymbl.reasoning import EpisodeEvidence, SonnetAnalyst, render_evidence
from grymbl.redact import REDACTED
from grymbl.store import Store
from grymbl.watch import make_analyst
from tests.helpers import at, command


class _Stdin:
    def __init__(self, text: str) -> None:
        self.buffer = io.BytesIO(text.encode("utf-8"))


def test_capture_command_stores_only_redacted_text(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Store(settings.db_path) as store:
        store.set_meta("developer", "dev")
    monkeypatch.chdir(settings.repo_root)
    monkeypatch.setattr(sys, "stdin", _Stdin("psql -h prod-db -U admin -p s3cr3t"))

    assert main(["capture-command", "--exit-code", "1"]) == 0

    with Store(settings.db_path) as store:
        [event] = store.unassigned_events()
    assert event.payload == {
        "command": f"psql -h prod-db -U admin -p {REDACTED}",
        "exit_code": 1,
    }
    assert b"s3cr3t" not in settings.db_path.read_bytes()


def test_capture_outside_watched_repo_is_a_silent_no_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", _Stdin("ls"))
    assert main(["capture-command", "--exit-code", "0"]) == 0
    assert not (tmp_path / ".grymbl").exists()


def test_evidence_sent_to_model_is_redacted_again() -> None:
    evidence = EpisodeEvidence(
        episode_id="e1",
        developer="dev",
        reasons=("fail -> retry -> pass",),
        events=[command("echo ghp_abcdefghijklmnopqrstuvwxyz0123", 0)],
        history=[],
    )
    rendered = render_evidence(evidence)
    assert "ghp_" not in rendered
    assert REDACTED in rendered
    assert at(0).strftime("%H:%M:%S") in rendered


def test_missing_credentials_do_not_crash_the_watcher(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("ANTHROPIC_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", "/nonexistent-grymbl-test")
    monkeypatch.setenv("USERPROFILE", "/nonexistent-grymbl-test")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/nonexistent-grymbl-test")
    monkeypatch.setenv("APPDATA", "/nonexistent-grymbl-test")
    analyst = SonnetAnalyst("claude-sonnet-5")
    evidence = EpisodeEvidence("e1", "dev", ("fail -> retry -> pass",), [command("ls", 0)], [])
    assert analyst.analyze(evidence) is None
    assert analyst.analyze(evidence) is None  # stays quiet after the first failure


def test_unresolvable_credentials_do_not_crash_the_watcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ANTHROPIC_CONFIG_DIR", "/nonexistent-grymbl-test")
    assert make_analyst(Settings(Path())) is None
