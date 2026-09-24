"""Test-runner sensor: structured output from pytest, Jest, and `go test` (plan §2)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Sequence, Set
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

from grymbl.config import to_repo_path
from grymbl.events import Event, EventKind, utcnow
from grymbl.store import Store


class Runner(StrEnum):
    PYTEST = "pytest"
    JEST = "jest"
    GO = "go"


@dataclass(frozen=True)
class TestRun:
    runner: Runner
    passed: int
    failed: int
    failed_tests: tuple[str, ...]
    files: tuple[str, ...]


class UnsupportedRunnerError(ValueError):
    pass


def detect_runner(argv: Sequence[str]) -> Runner:
    names = [PurePosixPath(arg.replace("\\", "/")).name for arg in argv]
    if any(name in ("pytest", "py.test", "pytest.exe") for name in names):
        return Runner.PYTEST
    if any(name in ("jest", "jest.js", "jest.cmd") for name in names):
        return Runner.JEST
    if names[:2] == ["go", "test"]:
        return Runner.GO
    raise UnsupportedRunnerError(
        "unsupported test command; use pytest, jest (e.g. `npx jest`), or `go test`"
    )


def run_and_capture(
    argv: Sequence[str], store: Store, developer: str, repo_root: Path, cwd: Path
) -> int:
    """Run the tests with structured output enabled, record the result, return its exit code."""
    runner = detect_runner(argv)
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        if runner is Runner.PYTEST:
            code = subprocess.run(
                [*argv, "--json-report", f"--json-report-file={report}"], cwd=cwd, check=False
            ).returncode
            run = parse_pytest(_load_json(report), cwd, repo_root) if report.exists() else None
        elif runner is Runner.JEST:
            code = subprocess.run(
                [*argv, "--json", f"--outputFile={report}"], cwd=cwd, check=False
            ).returncode
            run = parse_jest(_load_json(report), repo_root) if report.exists() else None
        else:
            code, lines = _run_go(argv, cwd)
            run = parse_go(lines, repo_root, store.known_files())
    if run is not None:
        record_test_run(store, developer, run)
    return code


def record_test_run(store: Store, developer: str, run: TestRun) -> Event:
    return store.add_event(
        Event(
            EventKind.TEST_RUN,
            utcnow(),
            developer,
            files=run.files,
            payload={
                "runner": run.runner.value,
                "passed": run.passed,
                "failed": run.failed,
                "failed_tests": list(run.failed_tests),
            },
        )
    )


def parse_pytest(report: dict[str, Any], cwd: Path, repo_root: Path) -> TestRun:
    """Parse a pytest-json-report file; node ids are relative to the pytest rootdir."""
    root = Path(report.get("root", cwd))
    tests = report.get("tests", [])
    failed = [t["nodeid"] for t in tests if t["outcome"] in ("failed", "error")]
    files = {
        path
        for t in tests
        if (path := to_repo_path(repo_root, root / t["nodeid"].split("::")[0])) is not None
    }
    summary = report.get("summary", {})
    return TestRun(
        runner=Runner.PYTEST,
        passed=int(summary.get("passed", 0)),
        failed=int(summary.get("failed", 0)) + int(summary.get("error", 0)),
        failed_tests=tuple(failed),
        files=tuple(sorted(files)),
    )


def parse_jest(report: dict[str, Any], repo_root: Path) -> TestRun:
    suites = report.get("testResults", [])
    failed = [
        assertion["fullName"]
        for suite in suites
        for assertion in suite.get("assertionResults", [])
        if assertion["status"] == "failed"
    ]
    files = {path for suite in suites if (path := to_repo_path(repo_root, Path(suite["name"])))}
    return TestRun(
        runner=Runner.JEST,
        passed=int(report.get("numPassedTests", 0)),
        failed=int(report.get("numFailedTests", 0))
        + int(report.get("numRuntimeErrorTestSuites", 0)),
        failed_tests=tuple(failed),
        files=tuple(sorted(files)),
    )


def parse_go(lines: Iterable[str], repo_root: Path, known_files: Set[str]) -> TestRun:
    """Parse `go test -json` output; packages map to their `_test.go` files."""
    passed = 0
    failed: list[str] = []
    packages: set[str] = set()
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        action, package, test = record.get("Action"), record.get("Package"), record.get("Test")
        if package:
            packages.add(package)
        if action == "pass" and test:
            passed += 1
        elif action == "fail" and (test or not _has_failed_tests(package, failed)):
            failed.append(f"{package}.{test}" if test else f"{package} (build or setup failure)")

    module = _go_module(repo_root)
    files: set[str] = set()
    for package in packages:
        directory = package.removeprefix(module).strip("/") if module else ""
        prefix = f"{directory}/" if directory else ""
        files |= {
            f
            for f in known_files
            if f.startswith(prefix) and "/" not in f[len(prefix) :] and f.endswith("_test.go")
        }
    return TestRun(Runner.GO, passed, len(failed), tuple(failed), tuple(sorted(files)))


def _has_failed_tests(package: str | None, failed: Sequence[str]) -> bool:
    return any(name.startswith(f"{package}.") for name in failed)


def _go_module(repo_root: Path) -> str | None:
    go_mod = repo_root / "go.mod"
    if not go_mod.exists():
        return None
    for line in go_mod.read_text(encoding="utf-8").splitlines():
        if line.startswith("module "):
            return line.split()[1]
    return None


def _run_go(argv: Sequence[str], cwd: Path) -> tuple[int, list[str]]:
    """Run `go test -json`, echoing the human-readable output as it streams."""
    process = subprocess.Popen(
        [*argv, "-json"], cwd=cwd, stdout=subprocess.PIPE, text=True, encoding="utf-8"
    )
    assert process.stdout is not None
    lines: list[str] = []
    for line in process.stdout:
        lines.append(line)
        try:
            output = json.loads(line).get("Output")
        except json.JSONDecodeError:
            output = line
        if output:
            sys.stdout.write(output)
    return process.wait(), lines


def _load_json(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data
