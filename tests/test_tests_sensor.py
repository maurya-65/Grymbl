from __future__ import annotations

import json
from pathlib import Path

import pytest

from grymbl.sensors.tests import (
    Runner,
    UnsupportedRunnerError,
    detect_runner,
    parse_go,
    parse_jest,
    parse_pytest,
)


def test_detect_runner() -> None:
    assert detect_runner(["pytest", "-x"]) is Runner.PYTEST
    assert detect_runner(["uv", "run", "pytest"]) is Runner.PYTEST
    assert detect_runner(["npx", "jest"]) is Runner.JEST
    assert detect_runner(["go", "test", "./..."]) is Runner.GO
    with pytest.raises(UnsupportedRunnerError):
        detect_runner(["make", "test"])


def test_parse_pytest(tmp_path: Path) -> None:
    report = {
        "root": str(tmp_path),
        "summary": {"passed": 1, "failed": 1, "total": 2},
        "tests": [
            {"nodeid": "tests/test_auth.py::test_ok", "outcome": "passed"},
            {"nodeid": "tests/test_auth.py::test_expiry", "outcome": "failed"},
        ],
    }
    run = parse_pytest(report, tmp_path, tmp_path)
    assert (run.passed, run.failed) == (1, 1)
    assert run.failed_tests == ("tests/test_auth.py::test_expiry",)
    assert run.files == ("tests/test_auth.py",)


def test_parse_jest(tmp_path: Path) -> None:
    report = {
        "numPassedTests": 2,
        "numFailedTests": 1,
        "testResults": [
            {
                "name": str(tmp_path / "web" / "login.test.ts"),
                "assertionResults": [
                    {"fullName": "login works", "status": "passed"},
                    {"fullName": "login rejects bad token", "status": "failed"},
                ],
            }
        ],
    }
    run = parse_jest(report, tmp_path)
    assert (run.passed, run.failed) == (2, 1)
    assert run.failed_tests == ("login rejects bad token",)
    assert run.files == ("web/login.test.ts",)


def test_parse_go(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text("module example.com/app\n\ngo 1.23\n", encoding="utf-8")
    lines = [
        json.dumps({"Action": "run", "Package": "example.com/app/auth", "Test": "TestA"}),
        json.dumps({"Action": "pass", "Package": "example.com/app/auth", "Test": "TestA"}),
        json.dumps({"Action": "fail", "Package": "example.com/app/auth", "Test": "TestB"}),
        json.dumps({"Action": "fail", "Package": "example.com/app/auth"}),
        "not json",
    ]
    known = {"auth/auth.go", "auth/auth_test.go", "auth/sub/x_test.go"}
    run = parse_go(lines, tmp_path, known)
    assert (run.passed, run.failed) == (1, 1)
    assert run.failed_tests == ("example.com/app/auth.TestB",)
    assert run.files == ("auth/auth_test.go",)
