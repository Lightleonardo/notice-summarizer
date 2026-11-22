"""Tests for notice_tool.checklist — rule-based notice checks (Step 4)."""

from pathlib import Path

from notice_tool import checklist

SAMPLES = Path("samples")


def _check(text, name):
    return next(c for c in checklist.notice_checklist(text) if c.name == name)


def test_audience():
    assert _check("Dear Parents, please come.", "audience").status == "ok"
    assert _check("The library is open.", "audience").status == "missing"


def test_date_exact_vs_relative_vs_missing():
    assert _check("Meeting on 8 December 2026.", "date").status == "ok"
    assert _check("Come to school soon.", "date").status == "weak"
    assert _check("Come to school.", "date").status == "missing"


def test_action():
    assert _check("Please bring your receipt.", "action").status == "ok"
    assert _check("The library is open daily.", "action").status == "missing"


def test_next_step():
    assert _check("Call 0803 123 4567.", "next_step").status == "ok"
    assert _check("Reply to confirm.", "next_step").status == "ok"
    assert _check("The library is open.", "next_step").status == "missing"


def test_weekday_match_is_ok():
    check = _check("Meeting on Tuesday, 8 December 2026.", "weekday_matches_date")
    assert check.status == "ok"


def test_weekday_mismatch_is_weak():
    check = _check("Workshop on Monday, 24 November 2026.", "weekday_matches_date")
    assert check.status == "weak"


def test_weekday_missing_when_no_pair():
    check = _check("Meeting on 8 December 2026.", "weekday_matches_date")
    assert check.status == "missing"


def test_every_check_has_a_suggestion_unless_ok():
    for check in checklist.notice_checklist((SAMPLES / "06_vague.txt").read_text(encoding="utf-8")):
        assert (check.suggestion is None) == (check.status == "ok")


def test_wrong_weekday_sample_is_flagged():
    text = (SAMPLES / "05_wrong_weekday.txt").read_text(encoding="utf-8")
    assert _check(text, "weekday_matches_date").status == "weak"


def test_vague_sample_is_flagged():
    text = (SAMPLES / "06_vague.txt").read_text(encoding="utf-8")
    assert _check(text, "date").status == "weak"
    assert _check(text, "next_step").status == "missing"
