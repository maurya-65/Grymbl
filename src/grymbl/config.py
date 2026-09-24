"""Paths and tunables for a watched repository."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path, PurePosixPath

DATA_DIR_NAME = ".grymbl"
SONNET_MODEL = "claude-sonnet-5"

IGNORED_DIRS = frozenset(
    {
        DATA_DIR_NAME,
        ".git",
        ".hg",
        ".idea",
        ".mypy_cache",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".vscode",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "node_modules",
        "venv",
    }
)
# Generated files whose churn says nothing about developer judgment.
IGNORED_NAMES = frozenset(
    {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "uv.lock", "poetry.lock", "go.sum"}
)
IGNORED_SUFFIXES = (".swp", ".swx", ".tmp", "~", ".pyc", ".log")
# Atomic-write temp files, e.g. Claude Code's `auth.py.tmp.4120.e60d016d67e1`.
_ATOMIC_TEMP = re.compile(r"\.tmp\.[\w.]+$")


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    # Episodes close after this much quiet time...
    idle_gap: timedelta = timedelta(minutes=5)
    # ...or this much after a failure, while the developer is still reading output.
    extended_gap: timedelta = timedelta(minutes=15)
    # Net meaningful lines removed from one file before it counts as deleted logic.
    deletion_threshold: int = 3
    max_file_bytes: int = 512_000
    model: str = SONNET_MODEL

    @property
    def data_dir(self) -> Path:
        return self.repo_root / DATA_DIR_NAME

    @property
    def db_path(self) -> Path:
        return self.data_dir / "grymbl.db"

    @property
    def interventions_path(self) -> Path:
        return self.data_dir / "interventions.md"

    @property
    def log_path(self) -> Path:
        return self.data_dir / "grymbl.log"


def find_repo_root(start: Path) -> Path | None:
    """Return the nearest ancestor of `start` that holds a Grymbl data dir."""
    start = start.resolve()
    for directory in (start, *start.parents):
        if (directory / DATA_DIR_NAME).is_dir():
            return directory
    return None


def to_repo_path(repo_root: Path, path: Path) -> str | None:
    """Repo-relative POSIX path, or None if `path` lies outside the repo."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None


def is_ignored(repo_path: str) -> bool:
    parts = PurePosixPath(repo_path).parts
    if any(part in IGNORED_DIRS for part in parts[:-1]):
        return True
    name = parts[-1] if parts else ""
    return (
        name in IGNORED_NAMES
        or name.endswith(IGNORED_SUFFIXES)
        or _ATOMIC_TEMP.search(name) is not None
    )
