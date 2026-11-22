"""Extract checkable facts from a notice.

Everything is normalised so that equivalent spellings compare equal later:

* dates   -> ``(month, day)`` pairs, e.g. ``(11, 24)`` for 24 November
* times   -> 24-hour ``"HH:MM"`` strings, e.g. ``"14:30"`` for 2.30 PM
* money   -> ``(currency, amount)`` tuples, e.g. ``("NGN", 8500.0)``
* phones  -> ten digits without the leading 0 or country code, e.g. ``"8031234567"``
* emails  -> lowercased
* urls    -> trailing full stop removed

Comparing these normalised values (not raw strings) is what lets a summary that
writes "Dec 3rd, 7.30am, N8,500" still match a notice that wrote
"3 December, 7:30 a.m., ₦8,500".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# --------------------------------------------------------------------------- #
# Dates
# --------------------------------------------------------------------------- #
MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

# Longest names first so "september" wins over "sep" and "march" over "mar".
_MONTH_ALT = "|".join(sorted(MONTHS, key=len, reverse=True))

# A month name, optionally abbreviated with a trailing full stop ("Nov.").
_MONTH_CAPTURE = rf"(?<![A-Za-z])({_MONTH_ALT})\.?(?![A-Za-z])"

# "8 December" / "24th of November" (+ optional ", 2026").  groups: (day, month)
_DAY_MONTH = re.compile(
    rf"(?<!\d)(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH_CAPTURE}(?:\s*,?\s*\d{{4}})?",
    re.IGNORECASE,
)

# "December 8" / "Nov. 24th" (+ optional ", 2026").  groups: (month, day)
_MONTH_DAY = re.compile(
    rf"{_MONTH_CAPTURE}\s+(\d{{1,2}})(?:st|nd|rd|th)?(?!\d)(?:\s*,?\s*\d{{4}})?",
    re.IGNORECASE,
)

# "8 to 12 December" / "8-12 December 2026".  groups: (d1, d2, month)
_DAY_RANGE_MONTH = re.compile(
    rf"(?<!\d)(\d{{1,2}})\s*(?:to|-|–)\s*(\d{{1,2}})\s+(?:of\s+)?{_MONTH_CAPTURE}",
    re.IGNORECASE,
)

# "24/11/2026" / "24.11.2026" — day first; a year is required.  groups: (day, month, year)
_NUMERIC_DATE = re.compile(r"(?<!\d)(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})(?!\d)")


def extract_dates(text: str) -> set[tuple[int, int]]:
    """Return every full date in ``text`` as a ``(month, day)`` pair."""
    found: set[tuple[int, int]] = set()

    for m in _DAY_RANGE_MONTH.finditer(text):
        month = MONTHS[m.group(3).lower()]
        found.add((month, int(m.group(1))))
        found.add((month, int(m.group(2))))

    for m in _DAY_MONTH.finditer(text):
        day = int(m.group(1))
        if 1 <= day <= 31:
            found.add((MONTHS[m.group(2).lower()], day))

    for m in _MONTH_DAY.finditer(text):
        day = int(m.group(2))
        if 1 <= day <= 31:
            found.add((MONTHS[m.group(1).lower()], day))

    for m in _NUMERIC_DATE.finditer(text):
        day, month = int(m.group(1)), int(m.group(2))
        if 1 <= day <= 31 and 1 <= month <= 12:
            found.add((month, day))

    return found


# --------------------------------------------------------------------------- #
# Times
# --------------------------------------------------------------------------- #
# 24-hour clock, e.g. "14:30".  The trailing lookahead stops it from also
# matching the "3:00" inside "3:00 p.m." (which the 12-hour pattern owns).
_TIME_24 = re.compile(
    r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)(?!\s*[ap]\.?\s?m)",
    re.IGNORECASE,
)

# 12-hour clock with am/pm, e.g. "8:00am", "8 a.m.", "2.30 PM".
_TIME_12 = re.compile(
    r"(?<![\d:])(\d{1,2})(?:[:.](\d{2}))?\s*([ap])\.?\s?m\.?(?![A-Za-z])",
    re.IGNORECASE,
)


def extract_times(text: str) -> set[str]:
    """Return every time in ``text`` as a 24-hour ``"HH:MM"`` string."""
    found: set[str] = set()

    for m in _TIME_24.finditer(text):
        found.add(f"{int(m.group(1)):02d}:{int(m.group(2)):02d}")

    for m in _TIME_12.finditer(text):
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        if not 1 <= hour <= 12:
            continue
        meridiem = m.group(3).lower()
        if meridiem == "p" and hour != 12:
            hour += 12
        elif meridiem == "a" and hour == 12:
            hour = 0
        found.add(f"{hour:02d}:{minute:02d}")

    return found


# --------------------------------------------------------------------------- #
# Money
# --------------------------------------------------------------------------- #
_MONEY_SYMBOL = [
    (re.compile(r"₦\s?([\d,]+(?:\.\d+)?)"), "NGN"),
    (re.compile(r"(?i)\bNGN\s?([\d,]+(?:\.\d+)?)"), "NGN"),
    (re.compile(r"\$\s?([\d,]+(?:\.\d+)?)"), "USD"),
    (re.compile(r"£\s?([\d,]+(?:\.\d+)?)"), "GBP"),
]

_MONEY_NAIRA_WORD = re.compile(r"(?i)\b([\d,]+(?:\.\d+)?)\s*naira\b")

# A bare "N" is ambiguous (naira or a class name), so it needs a thousands comma
# or at least three digits — see docs/decisions.md.
_MONEY_BARE_N = re.compile(r"(?<![A-Za-z])N\s?([\d,]+(?:\.\d+)?)")


def _to_amount(number: str) -> float:
    return float(number.replace(",", ""))


def extract_money(text: str) -> set[tuple[str, float]]:
    """Return every money amount in ``text`` as ``(currency, amount)``."""
    found: set[tuple[str, float]] = set()

    for pattern, currency in _MONEY_SYMBOL:
        for m in pattern.finditer(text):
            found.add((currency, _to_amount(m.group(1))))

    for m in _MONEY_NAIRA_WORD.finditer(text):
        found.add(("NGN", _to_amount(m.group(1))))

    for m in _MONEY_BARE_N.finditer(text):
        number = m.group(1)
        digits = re.sub(r"\D", "", number)
        if "," in number or len(digits) >= 3:
            found.add(("NGN", _to_amount(number)))

    return found


# --------------------------------------------------------------------------- #
# Phones
# --------------------------------------------------------------------------- #
# A run of digits (with spaces/hyphens/brackets/dots) that looks phone-like.
_PHONE_CANDIDATE = re.compile(r"\+?\d[\d\s\-().]{6,}\d")


def extract_phones(text: str) -> set[str]:
    """Return phone numbers normalised to ten digits (no leading 0 / country code)."""
    found: set[str] = set()

    for m in _PHONE_CANDIDATE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if digits.startswith("234") and len(digits) == 13:
            national = digits[3:]
        elif digits.startswith("0") and len(digits) == 11:
            national = digits[1:]
        else:
            continue
        if len(national) == 10 and national[0] in "789":
            found.add(national)

    return found


# --------------------------------------------------------------------------- #
# Emails and URLs
# --------------------------------------------------------------------------- #
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)


def extract_emails(text: str) -> set[str]:
    """Return every email address, lowercased."""
    return {m.group().lower() for m in _EMAIL.finditer(text)}


def extract_urls(text: str) -> set[str]:
    """Return every URL, with any trailing full stop removed."""
    return {m.group().rstrip(".") for m in _URL.finditer(text)}


# --------------------------------------------------------------------------- #
# Bundle
# --------------------------------------------------------------------------- #
@dataclass
class Facts:
    """All facts pulled out of one piece of text."""

    dates: set[tuple[int, int]] = field(default_factory=set)
    times: set[str] = field(default_factory=set)
    money: set[tuple[str, float]] = field(default_factory=set)
    phones: set[str] = field(default_factory=set)
    emails: set[str] = field(default_factory=set)
    urls: set[str] = field(default_factory=set)


def extract_facts(text: str) -> Facts:
    """Run every extractor over ``text`` and return the results together."""
    return Facts(
        dates=extract_dates(text),
        times=extract_times(text),
        money=extract_money(text),
        phones=extract_phones(text),
        emails=extract_emails(text),
        urls=extract_urls(text),
    )
