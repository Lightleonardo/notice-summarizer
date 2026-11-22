"""Accuracy checklist: compare a summary to its source notice.

Each check answers one question about whether the summary is *faithful* to the
notice, and returns ``pass``/``fail`` plus a short detail:

* ``dates_preserved`` / ``times_preserved`` / ``money_preserved`` /
  ``contacts_preserved`` - every fact in the notice also appears in the summary
* ``no_invented_facts``       - the summary adds no fact that is not in the notice
* ``prohibitions_kept``       - a forbidden thing in the notice stays forbidden
* ``evidence_quotes_found``   - each quoted piece of evidence is really in the notice
* ``shorter_than_notice``     - long notices are summarised to about 70% or less

Facts are compared *normalised* (see :mod:`notice_tool.facts`), so a summary
that writes "Dec 3rd, 7.30am, N8,500, 080-3123-4567" still matches a notice
that wrote "3 December, 7:30 a.m., ₦8,500, 08031234567".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from notice_tool.facts import Facts, extract_facts

# The length check only applies to notices longer than this many words.
WORD_THRESHOLD = 80
# ... and then the summary must be at most this share of the notice's length.
LENGTH_RATIO = 0.7

_PROHIBITION = re.compile(
    r"\b(do not|don't|must not|mustn't|should not|shouldn't|shall not|"
    r"not allowed|not permitted|prohibited|forbidden|banned|cannot|can't|"
    r"are not to|is not to|no phones|no mobile)\b",
    re.IGNORECASE,
)

_NEGATION = re.compile(
    r"\b(no|not|never|don't|do not|cannot|can't|mustn't|"
    r"prohibited|forbidden|banned|without)\b",
    re.IGNORECASE,
)


@dataclass
class CheckResult:
    """One accuracy check: its name, whether it passed, and a short detail."""

    name: str
    passed: bool
    detail: str


@dataclass
class ValidationReport:
    """The full set of checks for one summary/source pair."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True only when every check passed."""
        return all(check.passed for check in self.checks)

    def failed_checks(self) -> list[CheckResult]:
        return [check for check in self.checks if not check.passed]

    def failure_message(self) -> str:
        """A message listing every failure, suitable for a retry prompt."""
        failed = self.failed_checks()
        if not failed:
            return ""
        lines = ["The summary failed these checks; fix them and try again:"]
        lines += [f"- {check.name}: {check.detail}" for check in failed]
        return "\n".join(lines)


def _subset_check(name: str, label: str, expected: set, actual: set) -> CheckResult:
    missing = expected - actual
    if missing:
        return CheckResult(name, False, f"missing {label}: {_format(missing)}")
    return CheckResult(name, True, f"all {label} preserved")


def _format(values: set) -> str:
    return ", ".join(str(value) for value in sorted(values, key=str))


def _contacts(source: Facts) -> set:
    return source.phones | source.emails | source.urls


def _check_no_invented(source: Facts, summary: Facts) -> CheckResult:
    invented: list[str] = []
    groups = [
        ("date", source.dates, summary.dates),
        ("time", source.times, summary.times),
        ("amount", source.money, summary.money),
        ("contact", _contacts(source), _contacts(summary)),
    ]
    for label, notice_values, summary_values in groups:
        for value in sorted(summary_values - notice_values, key=str):
            invented.append(f"{label} {value}")
    if invented:
        return CheckResult(
            "no_invented_facts", False, "summary adds facts not in the notice: " + "; ".join(invented)
        )
    return CheckResult("no_invented_facts", True, "no invented facts")


def _check_prohibitions(source: str, summary: str) -> CheckResult:
    if not _PROHIBITION.search(source):
        return CheckResult("prohibitions_kept", True, "the notice has no prohibition")
    if _NEGATION.search(summary):
        return CheckResult("prohibitions_kept", True, "the prohibition is kept")
    return CheckResult(
        "prohibitions_kept",
        False,
        "the notice forbids something, but the summary has no negation",
    )


def _normalize_for_match(text: str) -> str:
    """Normalise whitespace and quotes so evidence quotes compare reliably."""
    for curly, straight in [("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"')]:
        text = text.replace(curly, straight)
    text = re.sub(r"\s+", " ", text).strip()
    return text.casefold()


def _check_evidence(source: str, evidence: list[str] | None) -> CheckResult:
    quotes = [quote for quote in (evidence or []) if quote and quote.strip()]
    if not quotes:
        return CheckResult("evidence_quotes_found", True, "no evidence quotes to check")
    haystack = _normalize_for_match(source)
    missing = [quote for quote in quotes if _normalize_for_match(quote) not in haystack]
    if missing:
        return CheckResult(
            "evidence_quotes_found",
            False,
            "evidence not found in the notice: " + "; ".join(missing),
        )
    return CheckResult("evidence_quotes_found", True, "all evidence quotes found")


def _check_shorter(source: str, summary: str) -> CheckResult:
    source_words = len(source.split())
    summary_words = len(summary.split())
    if source_words <= WORD_THRESHOLD:
        return CheckResult("shorter_than_notice", True, "the notice is short; length check skipped")
    limit = LENGTH_RATIO * source_words
    if summary_words <= limit:
        return CheckResult(
            "shorter_than_notice", True, f"{summary_words} words of {source_words}"
        )
    return CheckResult(
        "shorter_than_notice",
        False,
        f"summary is {summary_words} words of a {source_words}-word notice "
        f"(limit {limit:.0f})",
    )


def validate_summary(
    summary: str, source: str, *, evidence: list[str] | None = None
) -> ValidationReport:
    """Run every accuracy check comparing ``summary`` to ``source``."""
    notice_facts = extract_facts(source)
    summary_facts = extract_facts(summary)

    checks = [
        _subset_check("dates_preserved", "dates", notice_facts.dates, summary_facts.dates),
        _subset_check("times_preserved", "times", notice_facts.times, summary_facts.times),
        _subset_check("money_preserved", "amounts", notice_facts.money, summary_facts.money),
        _subset_check("contacts_preserved", "contacts", _contacts(notice_facts), _contacts(summary_facts)),
        _check_no_invented(notice_facts, summary_facts),
        _check_prohibitions(source, summary),
        _check_evidence(source, evidence),
        _check_shorter(source, summary),
    ]
    return ValidationReport(checks)
