"""Tests for notice_tool.facts — written test-first.

The expected values below are the cases I wrote down before implementing.
"""

import pytest

from notice_tool import facts


# --------------------------------------------------------------------------- #
# Dates -> (month, day) pairs
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text, expected",
    [
        # day then month name
        ("24 November 2026", {(11, 24)}),
        ("24th November", {(11, 24)}),
        ("Tuesday, 24 Nov.", {(11, 24)}),
        # month name then day
        ("November 24th, 2026", {(11, 24)}),
        ("Nov. 24", {(11, 24)}),
        # numeric, day first
        ("24/11/2026", {(11, 24)}),
        ("24.11.2026", {(11, 24)}),
        # ranges
        ("8 to 12 December", {(12, 8), (12, 12)}),
        ("8-12 December 2026", {(12, 8), (12, 12)}),
        ("1st December and 15th of January", {(12, 1), (1, 15)}),
        # not dates
        ("We resume on the 5th", set()),
        ("Room 12 to 15 pupils", set()),
        # known limit: dd/mm without a year is not recognised
        ("27/11", set()),
        # from the samples
        ("The meeting will hold on Tuesday, 8 December 2026.", {(12, 8)}),
        ("Report cards will be issued on 18 December 2026.", {(12, 18)}),
    ],
)
def test_extract_dates(text, expected):
    assert facts.extract_dates(text) == expected


# --------------------------------------------------------------------------- #
# Times -> 24-hour "HH:MM" strings
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text, expected",
    [
        ("8:00am", {"08:00"}),
        ("8 a.m.", {"08:00"}),
        ("2.30 PM", {"14:30"}),
        ("14:30", {"14:30"}),
        ("9am to 1pm", {"09:00", "13:00"}),
        ("12pm", {"12:00"}),
        ("12am", {"00:00"}),
        ("10:00 a.m.", {"10:00"}),
        ("7:30 a.m.", {"07:30"}),
        ("8:00 a.m. to 3:00 p.m.", {"08:00", "15:00"}),
    ],
)
def test_extract_times(text, expected):
    assert facts.extract_times(text) == expected


# --------------------------------------------------------------------------- #
# Money -> (currency, amount)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text, expected",
    [
        ("₦15,000", {("NGN", 15000.0)}),
        ("N15,000", {("NGN", 15000.0)}),
        ("NGN 15000", {("NGN", 15000.0)}),
        ("15,000 naira", {("NGN", 15000.0)}),
        ("₦2,500.50", {("NGN", 2500.5)}),
        ("$20", {("USD", 20.0)}),
        ("£5", {("GBP", 5.0)}),
        ("$20, £5", {("USD", 20.0), ("GBP", 5.0)}),
        # bare "N" needs three or more digits, or a thousands comma
        ("N500", {("NGN", 500.0)}),
        ("N5,000", {("NGN", 5000.0)}),
        ("₦50", {("NGN", 50.0)}),
        # not money
        ("Class N2 has 30 pupils", set()),
        ("Nursery N2 and N1", set()),
    ],
)
def test_extract_money(text, expected):
    assert facts.extract_money(text) == expected


# --------------------------------------------------------------------------- #
# Phones -> "8031234567"
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text, expected",
    [
        ("0803 123 4567", {"8031234567"}),
        ("08031234567", {"8031234567"}),
        ("0803-123-4567", {"8031234567"}),
        ("080-3123-4567", {"8031234567"}),
        ("+234 803 123 4567", {"8031234567"}),
        ("+2348031234567", {"8031234567"}),
        # not phones
        ("0123456789", set()),
        ("Room 0803", set()),
    ],
)
def test_extract_phones(text, expected):
    assert facts.extract_phones(text) == expected


# --------------------------------------------------------------------------- #
# Emails (lowercased) and URLs (trailing full stop removed)
# --------------------------------------------------------------------------- #
def test_extract_emails_lowercased():
    assert facts.extract_emails("Call MRS@Example.ORG now") == {"mrs@example.org"}


def test_extract_emails_ignores_trailing_full_stop():
    assert facts.extract_emails("email pta@example.org.") == {"pta@example.org"}


def test_extract_urls_strips_trailing_full_stop():
    assert facts.extract_urls("Visit https://example.org/info.") == {"https://example.org/info"}


def test_extract_urls_www():
    assert facts.extract_urls("see www.example.org.") == {"www.example.org"}


# --------------------------------------------------------------------------- #
# Combined
# --------------------------------------------------------------------------- #
def test_extract_facts_bundles_everything():
    got = facts.extract_facts(
        "PTA meeting on 8 December 2026 at 10:00 a.m. Pay ₦2,000. Call 0803 123 4567 "
        "or email pta@example.org."
    )
    assert got.dates == {(12, 8)}
    assert got.times == {"10:00"}
    assert got.money == {("NGN", 2000.0)}
    assert got.phones == {"8031234567"}
    assert got.emails == {"pta@example.org"}
