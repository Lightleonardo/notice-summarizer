"""Orchestration: notice in, checked summary out.

The flow:

1. Reject bad input: empty, too short (under :data:`MIN_WORDS` words), or too
   long (over :data:`MAX_WORDS` words).
2. Compute the rule-based checklist and the extractive baseline.
3. With no model configured, return the baseline (``extractive_only``).
4. Otherwise generate, validate, and on failure retry once with the validator's
   failure text in the prompt.
5. If it still fails - or the model raises anything - fall back to the baseline
   (``fallback_extractive``).
6. Log every failure to a JSONL file. We log a short hash of the notice, never
   the notice text itself.

A user can always override the result: :func:`apply_override` stores their
version, re-runs the validator, and logs the override with whether it passed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from notice_tool.baseline import BaselineSummary, baseline_summary
from notice_tool.checklist import Check, notice_checklist
from notice_tool.llm_summarizer import ParentSummary, summarize
from notice_tool.validator import ValidationReport, validate_summary

MIN_WORDS = 5
MAX_WORDS = 3000
DEFAULT_LOG_PATH = Path("logs") / "pipeline.jsonl"

STATUS_AI = "ai_validated"
STATUS_EXTRACTIVE_ONLY = "extractive_only"
STATUS_FALLBACK = "fallback_extractive"
STATUS_OVERRIDE = "user_override"


class InvalidNoticeError(ValueError):
    """Raised when the notice text is empty, too short, or too long."""


@dataclass
class PipelineResult:
    """Everything the app needs to display one summarisation run."""

    status: str
    source: str
    summary: str
    checklist: list[Check]
    baseline: BaselineSummary
    validation: ValidationReport
    ai_summary: ParentSummary | None = None
    error: str | None = None
    overridden: bool = False


# --------------------------------------------------------------------------- #
# Input validation
# --------------------------------------------------------------------------- #
def validate_notice(source: str) -> str:
    """Return the cleaned notice, or raise :class:`InvalidNoticeError`."""
    text = (source or "").strip()
    words = text.split()
    if not words:
        raise InvalidNoticeError("The notice is empty. Please paste the notice text.")
    if len(words) < MIN_WORDS:
        raise InvalidNoticeError(
            f"The notice is too short ({len(words)} words). "
            f"Please paste at least {MIN_WORDS} words."
        )
    if len(words) > MAX_WORDS:
        raise InvalidNoticeError(
            f"The notice is too long ({len(words)} words). The limit is {MAX_WORDS} words."
        )
    return text


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
def _notice_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]


def log_event(event: str, *, source: str, details: dict, log_path=DEFAULT_LOG_PATH) -> dict:
    """Append one JSON line describing ``event``. Never logs the notice text."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notice_hash": _notice_hash(source),
        "event": event,
        "details": details,
    }
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")
    return record


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _summary_text(ai: ParentSummary) -> str:
    """Render every content field of the AI summary into one checkable text."""
    parts = [ai.headline, ai.summary]
    parts += [f"{item.what}: {item.when}" for item in ai.key_dates]
    parts += [item.action for item in ai.actions]
    return " ".join(part for part in parts if part)


def _validate_ai(ai: ParentSummary, source: str) -> ValidationReport:
    return validate_summary(
        _summary_text(ai), source, evidence=[item.evidence for item in ai.actions]
    )


def _failure_names(report: ValidationReport) -> list[str]:
    return [check.name for check in report.failed_checks()]


def _fallback(
    text: str, checklist: list[Check], baseline: BaselineSummary, *, reason: str, log_path
) -> PipelineResult:
    log_event(
        STATUS_FALLBACK, source=text, details={"reason": reason}, log_path=log_path
    )
    return PipelineResult(
        status=STATUS_FALLBACK,
        source=text,
        summary=baseline.summary,
        checklist=checklist,
        baseline=baseline,
        validation=validate_summary(baseline.summary, text),
        ai_summary=None,
        error=reason,
    )


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
def run_pipeline(llm, source: str, *, log_path=DEFAULT_LOG_PATH) -> PipelineResult:
    """Run the full pipeline for ``source``.

    ``llm`` is a chat model (any object with ``with_structured_output``), or
    ``None`` to skip the model and use the extractive baseline only.
    """
    text = validate_notice(source)
    checklist = notice_checklist(text)
    baseline = baseline_summary(text)

    if llm is None:
        return PipelineResult(
            status=STATUS_EXTRACTIVE_ONLY,
            source=text,
            summary=baseline.summary,
            checklist=checklist,
            baseline=baseline,
            validation=validate_summary(baseline.summary, text),
        )

    # First attempt.
    try:
        ai = summarize(llm, text)
    except Exception as exc:  # noqa: BLE001 - any model failure must fall back safely
        reason = f"{type(exc).__name__}: {exc}"
        log_event("api_error", source=text, details={"attempt": 1, "reason": reason}, log_path=log_path)
        return _fallback(text, checklist, baseline, reason=reason, log_path=log_path)

    report = _validate_ai(ai, text)
    if report.passed:
        return PipelineResult(
            status=STATUS_AI,
            source=text,
            summary=_summary_text(ai),
            checklist=checklist,
            baseline=baseline,
            validation=report,
            ai_summary=ai,
        )

    # One retry, carrying the failure text.
    log_event(
        "validation_failed",
        source=text,
        details={"attempt": 1, "failures": _failure_names(report), "feedback": report.failure_message()},
        log_path=log_path,
    )
    try:
        ai = summarize(llm, text, feedback=report.failure_message())
    except Exception as exc:  # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"
        log_event("api_error", source=text, details={"attempt": 2, "reason": reason}, log_path=log_path)
        return _fallback(text, checklist, baseline, reason=reason, log_path=log_path)

    report = _validate_ai(ai, text)
    if report.passed:
        return PipelineResult(
            status=STATUS_AI,
            source=text,
            summary=_summary_text(ai),
            checklist=checklist,
            baseline=baseline,
            validation=report,
            ai_summary=ai,
        )

    log_event(
        "validation_failed",
        source=text,
        details={"attempt": 2, "failures": _failure_names(report), "feedback": report.failure_message()},
        log_path=log_path,
    )
    return _fallback(
        text, checklist, baseline, reason="Validation failed after a retry.", log_path=log_path
    )


# --------------------------------------------------------------------------- #
# User override
# --------------------------------------------------------------------------- #
def apply_override(
    result: PipelineResult, source: str, edited_text: str, *, log_path=DEFAULT_LOG_PATH
) -> PipelineResult:
    """Store the user's edited text, validate it, and log the override."""
    report = validate_summary(edited_text, source)
    log_event(
        "override",
        source=source,
        details={
            "passed": report.passed,
            "failures": _failure_names(report),
            "previous_status": result.status,
        },
        log_path=log_path,
    )
    return replace(
        result,
        status=STATUS_OVERRIDE,
        summary=edited_text,
        validation=report,
        overridden=True,
    )
