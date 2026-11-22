"""Rule-based checklist for a school notice.

Each check answers one plain question a parent would ask. A check is one of:

* ``ok``      - the notice clearly satisfies it
* ``weak``    - present but vague or inconsistent (e.g. "soon", wrong weekday)
* ``missing`` - nothing in the notice answers it

Every non-``ok`` check carries a short ``suggestion`` telling the author how to
fix it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from notice_tool.facts import MONTHS, extract_dates, extract_facts


@dataclass
class Check:
    """One checklist item: a name, its status, and a fix suggestion."""

    name: str
    status: str
    suggestion: str | None


_AUDIENCE = re.compile(r"\b(dear|to all|attention|parents?|guardians?)\b", re.IGNORECASE)

_RELATIVE_DATE = re.compile(
    r"\b(soon|today|tomorrow|tonight|next week|next month|this week|later|"
    r"shortly|as soon as possible|asap|coming days)\b",
    re.IGNORECASE,
)

_ACTION = re.compile(
    r"\b(bring|come|pay|attend|submit|reply|confirm|collect|register|ensure|"
    r"arrive|sign|return|send|complete|note|do not|must|should|required|"
    r"requested|compulsory)\b",
    re.IGNORECASE,
)

_NEXT_STEP = re.compile(
    r"\b(reply|confirm|submit|contact|call|email|visit|reach out|rsvp)\b",
    re.IGNORECASE,
)

_WEEKDAYS = [
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
]

# "Tuesday, 8 December 2026" / "Mon 24 Nov".  groups: (weekday, day, month, year)
_WEEKDAY_DATE = re.compile(
    r"(?<![A-Za-z])(" + "|".join(_WEEKDAYS) + r")s?[,\s]+"
    r"(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"([A-Za-z]{3,9})\.?"
    r"(?:\s*,?\s*(\d{4}))?",
    re.IGNORECASE,
)


def _audience(text: str) -> tuple[str, str | None]:
    if _AUDIENCE.search(text):
        return "ok", None
    return "missing", "Open with a greeting that names the audience, e.g. 'Dear Parents'."


def _date_check(text: str) -> tuple[str, str | None]:
    if extract_dates(text):
        return "ok", None
    if _RELATIVE_DATE.search(text):
        return "weak", "Replace vague words like 'soon' with an exact date (day, month, year)."
    return "missing", "Add the exact date (day, month, year) the notice refers to."


def _action_check(text: str) -> tuple[str, str | None]:
    if _ACTION.search(text):
        return "ok", None
    return "missing", "State clearly what parents are asked to do."


def _next_step_check(text: str) -> tuple[str, str | None]:
    facts = extract_facts(text)
    if facts.phones or facts.emails or facts.urls or _NEXT_STEP.search(text):
        return "ok", None
    return "missing", "Tell parents the next step, e.g. who to call or email, or what to reply."


def _weekday_check(text: str) -> tuple[str, str | None]:
    results: list[bool | None] = []
    for match in _WEEKDAY_DATE.finditer(text):
        given = match.group(1).lower()
        day = int(match.group(2))
        month = MONTHS.get(match.group(3).lower().rstrip("."))
        year = match.group(4)
        if month is None or not 1 <= day <= 31 or not year:
            results.append(None)
            continue
        try:
            actual = date(int(year), month, day).strftime("%A").lower()
        except ValueError:
            results.append(None)
            continue
        results.append(given == actual)

    if not results:
        return "missing", "Add the day of the week next to the date so parents can confirm it."
    if all(result is True for result in results):
        return "ok", None
    return "weak", "Check the weekday: it does not match the date given."


def notice_checklist(text: str) -> list[Check]:
    """Run every rule-based check over ``text`` and return them in order."""
    return [
        Check("audience", *_audience(text)),
        Check("date", *_date_check(text)),
        Check("action", *_action_check(text)),
        Check("next_step", *_next_step_check(text)),
        Check("weekday_matches_date", *_weekday_check(text)),
    ]
