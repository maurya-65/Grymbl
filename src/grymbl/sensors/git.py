"""Git sensor: native `post-commit` and `pre-push` hooks."""

from __future__ import annotations

import stat
import subprocess
from collections.abc import Sequence
from pathlib import Path

from grymbl.events import Event, EventKind, utcnow
from grymbl.redact import redact
from grymbl.store import Store

HOOK_MARKER = "# grymbl-hook"
HOOK_NAMES = ("post-commit", "pre-push")

# Hooks must never block a commit or push, and must stay quiet when grymbl is absent.
_HOOK_SCRIPT = f"""#!/bin/sh
{HOOK_MARKER}
command -v grymbl >/dev/null 2>&1 || exit 0
grymbl capture-git {{hook}} "$@" >/dev/null 2>&1 || true
exit 0
"""


def capture_commit(store: Store, developer: str, repo_root: Path) -> Event:
    sha = _git(repo_root, "rev-parse", "HEAD").strip()
    message = _git(repo_root, "log", "-1", "--format=%B").strip()
    changed = _git(repo_root, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "HEAD")
    return store.add_event(
        Event(
            EventKind.COMMIT,
            utcnow(),
            developer,
            files=tuple(line for line in changed.splitlines() if line),
            payload={"sha": sha, "message": redact(message)},
        )
    )


def capture_push(store: Store, developer: str, remote: str, stdin_lines: Sequence[str]) -> Event:
    """`stdin_lines` are git's `<local ref> <local sha> <remote ref> <remote sha>` lines."""
    refs = [f"{parts[0]} -> {parts[2]}" for line in stdin_lines if len(parts := line.split()) == 4]
    return store.add_event(
        Event(EventKind.PUSH, utcnow(), developer, payload={"remote": remote, "refs": refs})
    )


def install_hooks(repo_root: Path) -> list[str]:
    """Install hooks that are missing or already ours; returns a note per hook."""
    hooks_dir = repo_root / _git(repo_root, "rev-parse", "--git-path", "hooks").strip()
    hooks_dir.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    for name in HOOK_NAMES:
        hook = hooks_dir / name
        if hook.exists() and HOOK_MARKER not in hook.read_text(encoding="utf-8", errors="replace"):
            notes.append(
                f"skipped {name}: an existing hook is in place. Add this line to it:\n"
                f'  grymbl capture-git {name} "$@" >/dev/null 2>&1 || true'
            )
            continue
        hook.write_text(_HOOK_SCRIPT.format(hook=name), encoding="utf-8", newline="\n")
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        notes.append(f"installed {name}")
    return notes


def is_git_repo(path: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def git_toplevel(path: Path) -> Path:
    return Path(_git(path, "rev-parse", "--show-toplevel").strip())


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout
