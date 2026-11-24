"""Tests for notice_tool.pipeline.

Every test uses a scripted stand-in for the model, never the real API. The
scripted LLM records the prompts it receives and returns prepared outputs (or
raises a prepared exception), so we can drive the retry and fallback paths.
"""

import json

import pytest

from conftest import ScriptedLLM
from notice_tool.llm_summarizer import ActionItem, KeyDate, ParentSummary
from notice_tool.pipeline import InvalidNoticeError, apply_override, run_pipeline

NOTICE = (
    "Dear Parents. The PTA meeting holds on Tuesday, 8 December 2026 at "
    "10:00 a.m. Please bring your receipt booklet. Call 0803 123 4567."
)

GOOD_AI = ParentSummary(
    headline="PTA meeting",
    summary=(
        "PTA meeting on Tuesday, 8 December 2026 at 10:00 a.m. "
        "Bring your receipt booklet. Call 0803 123 4567."
    ),
    key_dates=[KeyDate(what="PTA meeting", when="8 December 2026 at 10:00 a.m.")],
    actions=[
        ActionItem(
            action="Bring your receipt booklet",
            evidence="Please bring your receipt booklet",
        )
    ],
)

DROPPED_DATE_AI = ParentSummary(
    headline="PTA meeting",
    summary="The PTA meeting is coming up in December. Bring your receipt booklet.",
    key_dates=[],
    actions=[
        ActionItem(
            action="Bring your receipt booklet",
            evidence="Please bring your receipt booklet",
        )
    ],
)


def _log_lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# --------------------------------------------------------------------------- #
# Input validation
# --------------------------------------------------------------------------- #
def test_empty_notice_is_rejected():
    with pytest.raises(InvalidNoticeError):
        run_pipeline(None, "   ")


def test_too_short_notice_is_rejected():
    with pytest.raises(InvalidNoticeError):
        run_pipeline(None, "Come to school.")


def test_too_long_notice_is_rejected():
    with pytest.raises(InvalidNoticeError):
        run_pipeline(None, "word " * 3001)


def test_valid_notice_is_accepted():
    result = run_pipeline(None, NOTICE)
    assert result.source.startswith("Dear Parents")


# --------------------------------------------------------------------------- #
# No model -> extractive only
# --------------------------------------------------------------------------- #
def test_no_model_returns_baseline():
    result = run_pipeline(None, NOTICE)
    assert result.status == "extractive_only"
    assert "8 December 2026" in result.summary
    assert result.baseline.original_words > 0
    assert result.validation.passed


# --------------------------------------------------------------------------- #
# Good AI summary passes first time
# --------------------------------------------------------------------------- #
def test_good_ai_summary_passes_first_attempt(tmp_path):
    llm = ScriptedLLM(GOOD_AI)
    result = run_pipeline(llm, NOTICE, log_path=tmp_path / "log.jsonl")
    assert result.status == "ai_validated"
    assert result.validation.passed
    assert len(llm.prompts) == 1
    assert "8 December 2026" in result.summary


# --------------------------------------------------------------------------- #
# Retry once, carrying the failure text
# --------------------------------------------------------------------------- #
def test_retry_after_dropped_date(tmp_path):
    llm = ScriptedLLM(DROPPED_DATE_AI, GOOD_AI)
    result = run_pipeline(llm, NOTICE, log_path=tmp_path / "log.jsonl")
    assert result.status == "ai_validated"
    assert len(llm.prompts) == 2
    assert "dates_preserved" in llm.prompts[1]


def test_fails_twice_falls_back_to_baseline(tmp_path):
    llm = ScriptedLLM(DROPPED_DATE_AI, DROPPED_DATE_AI)
    result = run_pipeline(llm, NOTICE, log_path=tmp_path / "log.jsonl")
    assert result.status == "fallback_extractive"
    assert result.summary == result.baseline.summary
    assert len(llm.prompts) == 2


# --------------------------------------------------------------------------- #
# API error -> fallback, logged
# --------------------------------------------------------------------------- #
def test_api_error_falls_back_and_logs(tmp_path):
    log_path = tmp_path / "log.jsonl"
    llm = ScriptedLLM(RuntimeError("the model is unavailable"))
    result = run_pipeline(llm, NOTICE, log_path=log_path)
    assert result.status == "fallback_extractive"
    assert "RuntimeError" in result.error
    events = [record["event"] for record in _log_lines(log_path)]
    assert "api_error" in events


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
def test_log_is_valid_json_lines(tmp_path):
    log_path = tmp_path / "log.jsonl"
    run_pipeline(ScriptedLLM(DROPPED_DATE_AI, DROPPED_DATE_AI), NOTICE, log_path=log_path)
    records = _log_lines(log_path)
    assert records
    for record in records:
        assert set(record) == {"timestamp", "notice_hash", "event", "details"}


def test_log_does_not_contain_the_notice_text(tmp_path):
    log_path = tmp_path / "log.jsonl"
    run_pipeline(ScriptedLLM(DROPPED_DATE_AI, DROPPED_DATE_AI), NOTICE, log_path=log_path)
    assert NOTICE not in log_path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Override
# --------------------------------------------------------------------------- #
def test_override_is_applied_and_logged(tmp_path):
    log_path = tmp_path / "log.jsonl"
    result = run_pipeline(None, NOTICE, log_path=log_path)
    edited = "Meeting on 8 December 2026. Bring your receipt booklet."

    overridden = apply_override(result, NOTICE, edited, log_path=log_path)

    assert overridden.summary == edited
    assert overridden.overridden is True
    events = [record["event"] for record in _log_lines(log_path)]
    assert "override" in events
    override_record = next(r for r in _log_lines(log_path) if r["event"] == "override")
    assert "passed" in override_record["details"]
