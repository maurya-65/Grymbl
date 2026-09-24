"""Sensors turn raw developer activity into normalized, redacted events."""

from __future__ import annotations

import getpass
import subprocess
from pathlib import Path

from grymbl.store import Store

_DEVELOPER_KEY = "developer"


def developer_name(store: Store, repo_root: Path) -> str:
    """The local developer, fixed at first use: git user.name, else the OS user."""
    if (name := store.get_meta(_DEVELOPER_KEY)) is not None:
        return name
    result = subprocess.run(
        ["git", "config", "user.name"], cwd=repo_root, capture_output=True, text=True, check=False
    )
    name = result.stdout.strip() or getpass.getuser()
    store.set_meta(_DEVELOPER_KEY, name)
    return name
