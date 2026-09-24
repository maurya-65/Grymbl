"""Exact content-hash dedup and diff statistics for file changes (plan §3)."""

from __future__ import annotations

import difflib
import hashlib
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


def count_meaningful(text: str) -> int:
    return sum(1 for line in text.splitlines() if is_meaningful(line))
