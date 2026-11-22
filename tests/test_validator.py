"""Tests for notice_tool.validator - the accuracy checklist (Step 5).

The validator compares a summary to its source and returns a report of checks,
each with a pass/fail and a short detail. These tests cover the cases named in
the brief: a good summary passes, each changed fact is caught, invented facts
are caught, a dropped prohibition is caught, fake evidence is caught, an
over-long summary is caught, and equivalent formats pass.
"""

from pathlib import Path

from notice_tool.baseline import baseline_summary
from notice_tool.validator import validate_summary

SAMPLES = sorted(Path("samples").glob("*.txt"))


def _check(report, name):
    return next(c for c in report.checks if c.name == name)


# --------------------------------------------------------------------------- #
# Good summary
# --------------------------------------------------------------------------- #
GOOD_SOURCE = (
    "Dear Parents. The PTA meeting holds on Tuesday, 8 December 2026 at "
    "10:00 a.m. Please bring your receipt booklet. Call 0803 123 4567 or "
    "email pta@example.org. Thank you."
)
GOOD_SUMMARY = (
    "PTA meeting on Tuesday, 8 December 2026 at 10:00 a.m. Bring your receipt "
    "booklet. Call 0803 123 4567 or email pta@example.org."
)


def test_good_summary_passes():
    report = validate_summary(GOOD_SUMMARY, GOOD_SOURCE)
    assert report.passed, report.failure_message()


# --------------------------------------------------------------------------- #
# Each changed fact is caught
# --------------------------------------------------------------------------- #
def test_changed_date_is_caught():
    report = validate_summary(
        "The meeting is on 4 December 2026.", "The meeting is on 3 December 2026."
    )
    assert not _check(report, "dates_preserved").passed
    assert not _check(report, "no_invented_facts").passed


def test_changed_time_is_caught():
    report = validate_summary("Starts at 10:00 a.m.", "Starts at 9:00 a.m.")
    assert not _check(report, "times_preserved").passed


def test_changed_amount_is_caught():
    report = validate_summary("The fee is ₦3,000.", "The fee is ₦2,000.")
    assert not _check(report, "money_preserved").passed


def test_changed_phone_is_caught():
    report = validate_summary("Call 0803 123 9999.", "Call 0803 123 4567.")
    assert not _check(report, "contacts_preserved").passed


def test_invented_fact_is_caught():
    report = validate_summary(
        "Meet on 3 December 2026 and pay ₦1,000.", "Meet on 3 December 2026."
    )
    assert not _check(report, "no_invented_facts").passed


# --------------------------------------------------------------------------- #
# Prohibitions
# --------------------------------------------------------------------------- #
def test_dropped_prohibition_is_caught():
    report = validate_summary(
        "Students may bring phones.", "Students are not allowed to bring phones."
    )
    assert not _check(report, "prohibitions_kept").passed


def test_kept_prohibition_passes():
    report = validate_summary(
        "Students must not bring phones.", "Students are not allowed to bring phones."
    )
    assert _check(report, "prohibitions_kept").passed


# --------------------------------------------------------------------------- #
# Evidence quotes
# --------------------------------------------------------------------------- #
def test_fake_evidence_is_caught():
    report = validate_summary(
        "Meeting on 3 December 2026.",
        "Meeting on 3 December 2026.",
        evidence=["Bring your receipt on Friday"],
    )
    assert not _check(report, "evidence_quotes_found").passed


def test_real_evidence_passes():
    report = validate_summary(
        "Bring your receipt.",
        "Please bring your receipt booklet.",
        evidence=["bring your receipt"],
    )
    assert _check(report, "evidence_quotes_found").passed


# --------------------------------------------------------------------------- #
# Length
# --------------------------------------------------------------------------- #
def test_over_long_summary_is_caught():
    source = "The meeting is on 3 December 2026. " + "filler words here. " * 30
    report = validate_summary(source, source)
    assert not _check(report, "shorter_than_notice").passed


def test_short_notice_skips_length_check():
    report = validate_summary("Meet on 3 December 2026.", "Meet on 3 December 2026.")
    assert _check(report, "shorter_than_notice").passed


# --------------------------------------------------------------------------- #
# Equivalent formats
# --------------------------------------------------------------------------- #
def test_equivalent_formats_pass():
    source = (
        "The exam is on 3 December 2026. Reporting time is 7:30 a.m. "
        "The fee is ₦8,500. Call 080-3123-4567."
    )
    summary = "Exam Dec 3rd. Report by 7.30am. Fee N8,500. Call 080-3123-4567."
    report = validate_summary(summary, source)
    assert _check(report, "dates_preserved").passed
    assert _check(report, "times_preserved").passed
    assert _check(report, "money_preserved").passed
    assert _check(report, "contacts_preserved").passed


# --------------------------------------------------------------------------- #
# Failure message (used for the retry prompt in Step 7)
# --------------------------------------------------------------------------- #
def test_failure_message_lists_failed_checks():
    report = validate_summary(
        "The meeting is on 4 December 2026.", "The meeting is on 3 December 2026."
    )
    assert "dates_preserved" in report.failure_message()


def test_passing_report_has_empty_failure_message():
    assert validate_summary(GOOD_SUMMARY, GOOD_SOURCE).failure_message() == ""


# --------------------------------------------------------------------------- #
# The extractive baseline is trustworthy by construction
# --------------------------------------------------------------------------- #
def test_baseline_output_passes_on_every_sample():
    for path in SAMPLES:
        text = path.read_text(encoding="utf-8")
        report = validate_summary(baseline_summary(text).summary, text)
        assert report.passed, (path.name, report.failure_message())
