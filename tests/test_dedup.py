from __future__ import annotations

from grymbl.dedup import content_hash, count_meaningful, diff_change


def test_identical_content_has_identical_hash() -> None:
    assert content_hash("a = 1\n") == content_hash("a = 1\n")
    assert content_hash("a = 1\n") != content_hash("a = 2\n")


def test_diff_counts_only_meaningful_lines() -> None:
    old = "def f():\n    return 1\n\n# note\n"
    new = "def f():\n    return 2\n"
    change = diff_change("m.py", old, new)
    assert change.added == 1
    assert change.removed == 1  # blank line and comment do not count
    assert "-    return 1" in change.diff


def test_new_file_is_all_additions() -> None:
    change = diff_change("m.py", None, "a = 1\nb = 2\n")
    assert (change.added, change.removed) == (2, 0)


def test_count_meaningful() -> None:
    assert count_meaningful("x = 1\n\n// c\ny()\n") == 2
