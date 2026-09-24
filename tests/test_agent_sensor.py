"""Claude Code hook capture. Payload shapes are copied from a real Claude Code 2.1 session."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from grymbl.config import Settings
from grymbl.events import EventKind
from grymbl.redact import REDACTED
from grymbl.sensors.agent import (
    CAPTURE_COMMAND,
    SETTINGS_FILE,
    capture_hook,
    install_claude_hooks,
    turn_narrative,
)
from grymbl.store import Store


def _hook(event: str, **fields: Any) -> dict[str, Any]:
    return {"session_id": "s1", "cwd": "/repo", "hook_event_name": event, **fields}


def test_prompt_is_recorded_redacted(store: Store, settings: Settings) -> None:
    hook = _hook("UserPromptSubmit", prompt="use key sk-ant-api03-abcdefghijklmnopqrstu to test")
    event = capture_hook(store, "dev", settings.repo_root, hook)
    assert event is not None and event.kind is EventKind.AGENT_PROMPT
    assert event.payload["prompt"] == f"use key {REDACTED} to test"
    assert event.payload["session_id"] == "s1"


def test_successful_bash_becomes_a_command(store: Store, settings: Settings) -> None:
    hook = _hook(
        "PostToolUse",
        tool_name="Bash",
        tool_input={"command": "export API_TOKEN=abc && pytest", "description": "Run tests"},
        tool_response={"stdout": "3 passed", "stderr": "", "interrupted": False},
    )
    event = capture_hook(store, "dev", settings.repo_root, hook)
    assert event is not None and event.kind is EventKind.COMMAND
    assert event.payload["command"] == f"export API_TOKEN={REDACTED} && pytest"
    assert event.payload["exit_code"] == 0
    assert event.payload["output_tail"] == "3 passed"
    assert not event.failed


def test_failed_bash_keeps_its_exit_code(store: Store, settings: Settings) -> None:
    hook = _hook(
        "PostToolUseFailure",
        tool_name="Bash",
        tool_input={"command": "ls does-not-exist", "description": "Run ls"},
        error="Exit code 2\nls: cannot access 'does-not-exist': No such file or directory",
    )
    event = capture_hook(store, "dev", settings.repo_root, hook)
    assert event is not None and event.failed
    assert event.payload["exit_code"] == 2


def test_file_edit_is_attributed_to_the_agent(store: Store, settings: Settings) -> None:
    target = settings.repo_root / "app" / "auth.py"
    hook = _hook("PostToolUse", tool_name="Edit", tool_input={"file_path": str(target)})
    event = capture_hook(store, "dev", settings.repo_root, hook)
    assert event is not None and event.kind is EventKind.AGENT_TOOL
    assert event.files == ("app/auth.py",)


def test_edits_outside_repo_and_read_only_tools_are_ignored(
    store: Store, settings: Settings, tmp_path: Path
) -> None:
    outside = _hook("PostToolUse", tool_name="Write", tool_input={"file_path": "/etc/hosts"})
    read = _hook("PostToolUse", tool_name="Read", tool_input={"file_path": "app/x.py"})
    assert capture_hook(store, "dev", settings.repo_root, outside) is None
    assert capture_hook(store, "dev", settings.repo_root, read) is None


def test_todo_list_is_captured_as_plan(store: Store, settings: Settings) -> None:
    todos = [{"content": "Fix token expiry", "status": "in_progress"}]
    hook = _hook("PostToolUse", tool_name="TodoWrite", tool_input={"todos": todos})
    event = capture_hook(store, "dev", settings.repo_root, hook)
    assert event is not None and event.payload["plan"] == "[in_progress] Fix token expiry"


def test_turn_end_reads_narrative_from_transcript(
    store: Store, settings: Settings, tmp_path: Path
) -> None:
    transcript = tmp_path / "t.jsonl"
    entries = [
        {"type": "user", "message": {"role": "user", "content": "old prompt"}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "old reply"}]}},
        {"type": "user", "message": {"role": "user", "content": "fix login"}},
        {"type": "assistant", "message": {"content": [{"type": "thinking", "thinking": ""}]}},
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "Assuming tokens last 1h."}]},
        },
        {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}},
        {
            "type": "assistant",
            "isSidechain": True,
            "message": {"content": [{"type": "text", "text": "subagent chatter"}]},
        },
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Done."}]}},
    ]
    transcript.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")

    hook = _hook("Stop", transcript_path=str(transcript), last_assistant_message="Done.")
    event = capture_hook(store, "dev", settings.repo_root, hook)
    assert event is not None and event.kind is EventKind.AGENT_TURN_END
    assert event.payload["narrative"] == "Assuming tokens last 1h.\n\nDone."


def test_turn_end_falls_back_to_last_message(store: Store, settings: Settings) -> None:
    hook = _hook("Stop", transcript_path="/missing.jsonl", last_assistant_message="All done.")
    event = capture_hook(store, "dev", settings.repo_root, hook)
    assert event is not None and event.payload["narrative"] == "All done."


def test_turn_narrative_skips_garbage_lines() -> None:
    assert turn_narrative(["not json", ""]) == []


def test_install_merges_into_existing_settings_idempotently(settings: Settings) -> None:
    path = settings.repo_root / SETTINGS_FILE
    path.parent.mkdir()
    existing = {"permissions": {"allow": ["Bash(ls:*)"]}, "hooks": {"Stop": [{"hooks": []}]}}
    path.write_text(json.dumps(existing), encoding="utf-8")

    install_claude_hooks(settings.repo_root)
    install_claude_hooks(settings.repo_root)

    config = json.loads(path.read_text(encoding="utf-8"))
    assert config["permissions"] == {"allow": ["Bash(ls:*)"]}
    for event_name in ("UserPromptSubmit", "PostToolUse", "PostToolUseFailure", "Stop"):
        commands = [
            hook["command"] for group in config["hooks"][event_name] for hook in group["hooks"]
        ]
        assert commands.count(CAPTURE_COMMAND) == 1
    assert config["hooks"]["PostToolUse"][0]["matcher"] == "*"


def test_stop_hook_is_synchronous_and_old_installs_are_upgraded(settings: Settings) -> None:
    path = settings.repo_root / SETTINGS_FILE
    path.parent.mkdir()
    old_hook = {"type": "command", "command": CAPTURE_COMMAND, "async": True}
    path.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [old_hook]}]}}), encoding="utf-8")

    assert "installed" in install_claude_hooks(settings.repo_root)
    assert "already" in install_claude_hooks(settings.repo_root)

    config = json.loads(path.read_text(encoding="utf-8"))
    [stop_group] = config["hooks"]["Stop"]
    assert "async" not in stop_group["hooks"][0]
    assert config["hooks"]["PostToolUse"][0]["hooks"][0]["async"] is True
