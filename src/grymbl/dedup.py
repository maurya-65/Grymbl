"""Exact content-hash dedup and diff statistics for file changes (plan §3)."""

from __future__ import annotations

import difflib
import hashlib
import re
from dataclasses import dataclass

_COMMENT_PREFIXES = ("#", "//", "/*", "*", "--")


@dataclass(frozen=True)
class FileChange:
    path: str
    diff: str
    added: int
    removed: int


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_meaningful(line: str) -> bool:
    """A line that carries logic: not blank, not a comment."""
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith(_COMMENT_PREFIXES)


def diff_change(path: str, old: str | None, new: str) -> FileChange:
    """Diff `old` (None for a new file) against `new`, counting meaningful lines."""
    old_lines = (old or "").splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}")
    )
    added = sum(
        1
        for line in diff_lines
        if line.startswith("+") and not line.startswith("+++") and is_meaningful(line[1:])
    )
    removed = sum(
        1
        for line in diff_lines
        if line.startswith("-") and not line.startswith("---") and is_meaningful(line[1:])
    )
    return FileChange(path=path, diff="".join(diff_lines), added=added, removed=removed)


def unapply(new: str, diff: str) -> str | None:
    """The text `diff` (from `diff_change`) was made from, or None if `new` doesn't match it.

    Every context and added line is checked, so a snapshot that drifted from the recorded
    history (say, edited while `grymbl watch` was stopped) fails instead of guessing.
    """
    new_lines = new.splitlines(keepends=True)
    old_lines: list[str] = []
    cursor = 0
    hunks = _HUNK.split(diff)
    # split() alternates: preamble, then (old_count, new_start, new_count, body) per hunk.
    for i in range(1, len(hunks), 4):
        old_count, start, new_count, body = hunks[i : i + 4]
        # Unified ranges are 1-based, except an empty range names the line before it.
        index = int(start) if new_count == "0" else int(start) - 1
        before: list[str] = []
        after: list[str] = []
        for line in body.splitlines(keepends=True):
            if line.startswith((" ", "-")):
                before.append(line[1:])
            if line.startswith((" ", "+")):
                after.append(line[1:])
            if not line.startswith((" ", "-", "+")):
                return None
        # A last line without a newline runs into the next diff line; the counts catch it.
        if (len(before), len(after)) != (int(old_count or 1), int(new_count or 1)):
            return None
        if index < cursor or new_lines[index : index + len(after)] != after:
            return None
        old_lines += new_lines[cursor:index] + before
        cursor = index + len(after)
    return "".join(old_lines + new_lines[cursor:])


_HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*\n", re.M)


def count_meaningful(text: str) -> int:
    return sum(1 for line in text.splitlines() if is_meaningful(line))
