from __future__ import annotations

from grymbl.dedup import content_hash, count_meaningful, diff_change, unapply


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


def test_unapply_recovers_the_old_text() -> None:
    old = "a\nb\nc\nd\ne\nf\ng\nh\n"
    new = "a\nB\nc\nd\ne\nf\ng\nh\ni\n"
    assert unapply(new, diff_change("m.py", old, new).diff) == old
    assert unapply("x = 1\n", diff_change("m.py", None, "x = 1\n").diff) == ""


def test_unapply_refuses_text_that_drifted_from_the_diff() -> None:
    diff = diff_change("m.py", "x = 1\ny = 2\n", "x = 1\ny = 3\n").diff
    assert unapply("x = 1\ny = 4\n", diff) is None


def test_unapply_refuses_a_missing_final_newline_instead_of_guessing() -> None:
    # difflib runs "-b" and "+c" together when the old last line has no newline.
    old, new = "a\nb", "a\nc\n"
    assert unapply(new, diff_change("m.py", old, new).diff) is None


def test_count_meaningful() -> None:
    assert count_meaningful("x = 1\n\n// c\ny()\n") == 2
