"""Jev: cheap, deterministic triage. No LLM, no ML (plan §6).

An episode escalates to Sonnet if ANY rule fires; otherwise it is recorded as routine
and nothing else happens. Silence is the default outcome.
"""

from __future__ import annotations

import fnmatch
from collections import defaultdict
from collections.abc import Sequence, Set
from dataclasses import dataclass
from pathlib import PurePosixPath

from grymbl.events import Event, EventKind

_TEST_DIRS = frozenset({"test", "tests", "__tests__", "spec", "specs", "e2e"})
_TEST_FILE_PATTERNS = (
    "test_*.py",
    "*_test.py",
    "conftest.py",
    "*_test.go",
    "*.test.*",
    "*.spec.*",
)
# Layout directories that hold modules rather than being one; look one level deeper.
_CONTAINER_DIRS = frozenset({"src", "lib", "app", "apps", "packages", "pkg", "internal", "cmd"})
_ROOT_MODULE = "."


# Stable identifiers for the four rules, stored per episode for reporting.
PRIOR_HISTORY = "prior_history"
FAIL_RETRY_PASS = "fail_retry_pass"
MULTIPLE_MODULES = "multiple_modules"
DELETED_LOGIC = "deleted_logic"


@dataclass(frozen=True)
class Triage:
    escalate: bool
    reasons: tuple[str, ...]
    had_deletion: bool
    had_fail_retry_pass: bool
    rules: tuple[str, ...] = ()


def triage(
    events: Sequence[Event],
    prior_escalated_files: Set[str],
    deletion_threshold: int,
) -> Triage:
    files = {path for event in events for path in event.files}
    deletion = had_deletion(events, deletion_threshold)
    fail_retry_pass = had_fail_retry_pass(events)
    modules = modules_touched(files)

    fired: list[tuple[str, str]] = []
    if with_history := sorted(files & prior_escalated_files):
        fired.append((PRIOR_HISTORY, f"prior history on {', '.join(with_history)}"))
    if fail_retry_pass:
        fired.append((FAIL_RETRY_PASS, "fail -> retry -> pass"))
    if len(modules) > 1:
        fired.append((MULTIPLE_MODULES, f"touches multiple modules: {', '.join(sorted(modules))}"))
    if deletion:
        fired.append((DELETED_LOGIC, "deletes existing logic"))
    return Triage(
        escalate=bool(fired),
        reasons=tuple(reason for _, reason in fired),
        had_deletion=deletion,
        had_fail_retry_pass=fail_retry_pass,
        rules=tuple(rule for rule, _ in fired),
    )


def had_fail_retry_pass(events: Sequence[Event]) -> bool:
    """A test run fails and a later one passes, or a command fails and later succeeds."""
    tests_failed = False
    failed_commands: set[str] = set()
    for event in events:
        if event.kind is EventKind.TEST_RUN:
            if event.failed:
                tests_failed = True
            elif tests_failed:
                return True
        elif event.kind is EventKind.COMMAND:
            command = str(event.payload["command"])
            if event.failed:
                failed_commands.add(command)
            elif command in failed_commands:
                return True
    return False


def had_deletion(events: Sequence[Event], threshold: int) -> bool:
    """A file with logic was deleted, or one lost `threshold`+ net meaningful lines."""
    net_removed: defaultdict[str, int] = defaultdict(int)
    for event in events:
        if event.kind is EventKind.FILE_DELETED and int(event.payload["removed"]) > 0:
            return True
        if event.kind is EventKind.FILE_CHANGED:
            path = event.files[0]
            net_removed[path] += int(event.payload["removed"]) - int(event.payload["added"])
    return any(n >= threshold for n in net_removed.values())


def modules_touched(files: Set[str]) -> set[str]:
    """Distinct top-level modules, ignoring tests so `auth.py` + `test_auth.py` is one."""
    return {module for path in files if (module := module_of(path)) is not None}


def module_of(path: str) -> str | None:
    if is_test_path(path):
        return None
    directories = PurePosixPath(path).parts[:-1]
    if not directories:
        return _ROOT_MODULE
    if directories[0] in _CONTAINER_DIRS and len(directories) > 1:
        return f"{directories[0]}/{directories[1]}"
    return directories[0]


def is_test_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if any(part in _TEST_DIRS for part in parts[:-1]):
        return True
    return any(fnmatch.fnmatch(parts[-1], pattern) for pattern in _TEST_FILE_PATTERNS)
