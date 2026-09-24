from __future__ import annotations

from grymbl.events import Event, EventKind
from grymbl.jev import is_test_path, module_of, triage
from tests.helpers import at, change, command, ran_tests


def test_routine_episode_stays_silent() -> None:
    result = triage([change("app/auth.py", 0), ran_tests(1, failed=0)], set(), 3)
    assert not result.escalate
    assert result.reasons == ()


def test_rule_1_prior_escalated_history() -> None:
    result = triage([change("app/auth.py", 0)], {"app/auth.py"}, 3)
    assert result.escalate
    assert "prior history" in result.reasons[0]


def test_rule_2_fail_retry_pass_on_tests() -> None:
    events = [ran_tests(0, failed=1), change("app/auth.py", 1), ran_tests(2, failed=0)]
    result = triage(events, set(), 3)
    assert result.escalate and result.had_fail_retry_pass


def test_rule_2_fail_retry_pass_on_commands() -> None:
    events = [command("make build", 0, exit_code=2), command("make build", 1, exit_code=0)]
    assert triage(events, set(), 3).had_fail_retry_pass


def test_pass_then_fail_is_not_fail_retry_pass() -> None:
    assert not triage([ran_tests(0, failed=0), ran_tests(1, failed=1)], set(), 3).escalate


def test_rule_3_multiple_modules_ignores_tests() -> None:
    same = triage([change("app/auth.py", 0), change("tests/test_auth.py", 1)], set(), 3)
    assert not same.escalate
    multi = triage([change("app/auth.py", 0), change("web/login.ts", 1)], set(), 3)
    assert multi.escalate and "multiple modules" in multi.reasons[0]


def test_rule_4_deletion_accumulates_per_file() -> None:
    events = [change("app/auth.py", 0, added=0, removed=2), change("app/auth.py", 1, 0, 2)]
    assert triage(events, set(), 3).had_deletion


def test_rule_4_replacement_is_not_deletion() -> None:
    assert not triage([change("app/auth.py", 0, added=5, removed=5)], set(), 3).had_deletion


def test_rule_4_deleting_a_file_with_logic() -> None:
    deleted = Event(EventKind.FILE_DELETED, at(0), "dev", ("app/old.py",), {"removed": 12})
    assert triage([deleted], set(), 3).had_deletion


def test_module_of_looks_inside_container_dirs() -> None:
    assert module_of("src/auth/login.py") == "src/auth"
    assert module_of("app/auth.py") == "app"
    assert module_of("README.md") == "."
    assert module_of("tests/test_auth.py") is None


def test_is_test_path() -> None:
    assert is_test_path("web/Login.test.tsx")
    assert is_test_path("pkg/auth_test.go")
    assert is_test_path("__tests__/a.js")
    assert not is_test_path("app/testing_utils.py")
