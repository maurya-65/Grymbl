"""Coding-agent sensor: Claude Code hooks (v1.1 addendum, step 1).

Passive capture only: the prompt that set the intent, what the agent ran and edited, and
what it said about its work. Everything is redacted before storage. What the agent says is
a claim, not evidence; Sonnet is told as much.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from grymbl.config import is_ignored, to_repo_path
from grymbl.events import Event, EventKind, utcnow
from grymbl.redact import redact
from grymbl.sensors.terminal import is_self_command
from grymbl.store import Store

AGENT = "claude-code"
CAPTURE_COMMAND = "grymbl capture-agent"
SETTINGS_FILE = Path(".claude") / "settings.local.json"

_HOOK_EVENTS = ("UserPromptSubmit", "PostToolUse", "PostToolUseFailure", "Stop")
_FILE_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
_EXIT_CODE = re.compile(r"^Exit code (\d+)")
_OUTPUT_TAIL_LINES = 30
# Per-turn cap on stored narrative; long turns keep the start and say so.
_NARRATIVE_LIMIT = 20_000


def capture_hook(
    store: Store, developer: str, repo_root: Path, hook: Mapping[str, Any]
) -> Event | None:
    """Turn one Claude Code hook payload into an event, if it is one we record."""
    context = {"agent": AGENT, "session_id": str(hook.get("session_id", ""))}
    match hook.get("hook_event_name"):
        case "UserPromptSubmit":
            prompt = str(hook.get("prompt", "")).strip()
            if not prompt:
                return None
            return _add(
                store, developer, EventKind.AGENT_PROMPT, (), prompt=redact(prompt), **context
            )
        case "PostToolUse" | "PostToolUseFailure":
            return _capture_tool(store, developer, repo_root, hook, context)
        case "Stop":
            narrative = _narrative(hook)
            if not narrative:
                return None
            return _add(
                store, developer, EventKind.AGENT_TURN_END, (), narrative=narrative, **context
            )
    return None


def _capture_tool(
    store: Store,
    developer: str,
    repo_root: Path,
    hook: Mapping[str, Any],
    context: dict[str, str],
) -> Event | None:
    tool = str(hook.get("tool_name", ""))
    tool_input: Mapping[str, Any] = hook.get("tool_input") or {}
    failed = hook.get("hook_event_name") == "PostToolUseFailure"

    if tool == "Bash":
        command = str(tool_input.get("command", "")).strip()
        if not command or is_self_command(command):
            return None
        exit_code, output = _bash_result(hook, failed)
        return _add(
            store,
            developer,
            EventKind.COMMAND,
            (),
            command=redact(command),
            exit_code=exit_code,
            description=redact(str(tool_input.get("description", ""))),
            output_tail=redact(_tail(output)),
            **context,
        )
    if tool in _FILE_TOOLS:
        raw_path = tool_input.get("file_path") or tool_input.get("notebook_path")
        path = to_repo_path(repo_root, Path(str(raw_path))) if raw_path else None
        if path is None or is_ignored(path):
            return None
        return _add(
            store, developer, EventKind.AGENT_TOOL, (path,), tool=tool, failed=failed, **context
        )
    if tool == "TodoWrite":
        plan = [
            f"[{todo.get('status', '?')}] {todo.get('content', '')}"
            for todo in tool_input.get("todos", [])
        ]
        return _add(
            store,
            developer,
            EventKind.AGENT_TOOL,
            (),
            tool=tool,
            plan=redact("\n".join(plan)),
            **context,
        )
    return None


def _bash_result(hook: Mapping[str, Any], failed: bool) -> tuple[int, str]:
    if failed:
        error = str(hook.get("error", ""))
        match = _EXIT_CODE.match(error)
        return (int(match.group(1)) if match else 1), error
    response: Mapping[str, Any] = hook.get("tool_response") or {}
    output = "\n".join(s for s in (response.get("stdout"), response.get("stderr")) if s)
    return (130 if response.get("interrupted") else 0), output


def _narrative(hook: Mapping[str, Any]) -> str:
    """Everything the agent wrote this turn, from the transcript when readable."""
    texts: list[str] = []
    if transcript := hook.get("transcript_path"):
        try:
            with Path(str(transcript)).open(encoding="utf-8") as lines:
                texts = turn_narrative(lines)
        except OSError:
            texts = []
    if not texts and (last := hook.get("last_assistant_message")):
        texts = [str(last)]
    narrative = "\n\n".join(texts).strip()
    if len(narrative) > _NARRATIVE_LIMIT:
        narrative = narrative[:_NARRATIVE_LIMIT] + "\n[narrative truncated by grymbl]"
    return redact(narrative)


def turn_narrative(transcript_lines: Iterable[str]) -> list[str]:
    """Assistant text (and any visible thinking) since the last real user prompt."""
    texts: list[str] = []
    for line in transcript_lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("isSidechain"):
            continue
        message = entry.get("message") or {}
        content = message.get("content")
        if entry.get("type") == "user" and _is_prompt(content):
            texts = []
        elif entry.get("type") == "assistant" and isinstance(content, list):
            for block in content:
                if block.get("type") == "text" and block.get("text", "").strip():
                    texts.append(block["text"].strip())
                elif block.get("type") == "thinking" and (block.get("thinking") or "").strip():
                    texts.append(f"(thinking) {block['thinking'].strip()}")
    return texts


def _is_prompt(content: object) -> bool:
    if isinstance(content, str):
        return True
    return isinstance(content, list) and not any(
        isinstance(block, dict) and block.get("type") == "tool_result" for block in content
    )


def _tail(text: str) -> str:
    return "\n".join(text.splitlines()[-_OUTPUT_TAIL_LINES:])


def _add(
    store: Store, developer: str, kind: EventKind, files: tuple[str, ...], **payload: Any
) -> Event:
    return store.add_event(Event(kind, utcnow(), developer, files, payload))


def install_claude_hooks(repo_root: Path) -> str:
    """Add Grymbl's hooks to the repo's local (gitignored) Claude Code settings."""
    settings_path = repo_root / SETTINGS_FILE
    settings: dict[str, Any] = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return f"skipped Claude Code hooks: {SETTINGS_FILE} is not valid JSON"

    original = json.dumps(settings, sort_keys=True)
    hooks: dict[str, list[dict[str, Any]]] = settings.setdefault("hooks", {})
    for event_name in _HOOK_EVENTS:
        # Replace any earlier Grymbl entry so re-running init upgrades it in place.
        groups = [
            {**group, "hooks": others}
            for group in hooks.get(event_name, [])
            if (
                others := [h for h in group.get("hooks", []) if h.get("command") != CAPTURE_COMMAND]
            )
            or not group.get("hooks")
        ]
        groups.append(_hook_group(event_name))
        hooks[event_name] = groups

    if json.dumps(settings, sort_keys=True) == original:
        status = "already in"
    else:
        settings_path.parent.mkdir(exist_ok=True)
        settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        status = "installed in"
    _keep_out_of_git(repo_root, SETTINGS_FILE)
    return f"Claude Code hooks {status} {SETTINGS_FILE.as_posix()}"


def _hook_group(event_name: str) -> dict[str, Any]:
    # Stop runs synchronously: background hooks are dropped when a headless session exits,
    # and reading the transcript takes milliseconds. Everything else stays off the agent's path.
    hook = {"type": "command", "command": CAPTURE_COMMAND, "timeout": 10}
    if event_name != "Stop":
        hook["async"] = True
    group: dict[str, Any] = {"hooks": [hook]}
    if event_name.startswith("PostToolUse"):
        group = {"matcher": "*", **group}
    return group


def _keep_out_of_git(repo_root: Path, path: Path) -> None:
    """Local settings must never be committed; add a local exclude if nothing ignores them."""
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", path.as_posix()], cwd=repo_root, check=False
    )
    if ignored.returncode != 1:  # 0 = already ignored, 128 = not a git repo
        return
    exclude = subprocess.run(
        ["git", "rev-parse", "--git-path", "info/exclude"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    exclude_path = repo_root / exclude
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    with exclude_path.open("a", encoding="utf-8") as file:
        file.write(f"\n/{path.as_posix()}\n")
