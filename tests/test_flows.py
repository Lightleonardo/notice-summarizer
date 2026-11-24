"""Core end-to-end flows.

These run the full pipeline end to end - input validation, checklist, baseline,
the model call, the validator, the one retry, the fallback, the log, and the
overriding of the result - over the real notices in ``samples/``. They use
``ScriptedLLM``, a stand-in that returns prepared outputs (or raises a prepared
exception), so no test ever calls the real API.

The per-branch unit tests are in ``test_pipeline.py``; this file is the
integration-level one.
"""

import json
from pathlib import Path

import pytest

from conftest import ScriptedLLM
from notice_tool.llm_summarizer import ActionItem, KeyDate, ParentSummary
from notice_tool.pipeline import InvalidNoticeError, apply_override, run_pipeline

SAMPLES = sorted(Path("samples").glob("*.txt"))
PTA_NOTICE = (Path("samples") / "01_pta_meeting.txt").read_text(encoding="utf-8")

# A faithful summary of sample 01: every fact in the notice is preserved.
PTA_GOOD = ParentSummary(
    headline="PTA meeting on 8 December 2026",
    summary=(
        "PTA meeting on Tuesday, 8 December 2026 at 10:00 a.m. in the school hall. "
        "A voluntary \u20a62,000 contribution per family is requested. "
        "Please bring your receipt booklet. "
        "For enquiries call 0803 123 4567 or email pta@example.org."
    ),
    key_dates=[KeyDate(what="PTA meeting", when="8 December 2026 at 10:00 a.m.")],
    actions=[
        ActionItem(
            action="Bring your receipt booklet",
            evidence="Please bring your receipt booklet",
        )
    ],
)

# The same summary with the date - and every other fact - dropped.
PTA_DROPPED_DATE = ParentSummary(
    headline="PTA meeting",
    summary="The PTA meeting is coming up soon. Please bring your receipt booklet.",
    key_dates=[],
    actions=[
        ActionItem(
            action="Bring your receipt booklet",
            evidence="Please bring your receipt booklet",
        )
    ],
)


def _log_lines(path):
    text = Path(path).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


# --------------------------------------------------------------------------- #
# The baseline is trustworthy by construction, on every sample
# --------------------------------------------------------------------------- #
def test_baseline_never_loses_a_fact_on_every_sample():
    for path in SAMPLES:
        notice = path.read_text(encoding="utf-8")
        result = run_pipeline(None, notice)
        assert result.status == "extractive_only"
        assert result.validation.passed, (path.name, result.validation.failure_message())


# --------------------------------------------------------------------------- #
# A good AI summary passes on the first attempt
# --------------------------------------------------------------------------- #
def test_good_ai_summary_passes_on_the_first_attempt(tmp_path):
    llm = ScriptedLLM(PTA_GOOD)
    result = run_pipeline(llm, PTA_NOTICE, log_path=tmp_path / "log.jsonl")
    assert result.status == "ai_validated"
    assert result.validation.passed
    assert len(llm.prompts) == 1


# --------------------------------------------------------------------------- #
# A dropped date triggers one retry that carries the failure text
# --------------------------------------------------------------------------- #
def test_dropped_date_is_retried_with_the_failure_text(tmp_path):
    llm = ScriptedLLM(PTA_DROPPED_DATE, PTA_GOOD)
    result = run_pipeline(llm, PTA_NOTICE, log_path=tmp_path / "log.jsonl")
    assert result.status == "ai_validated"
    assert len(llm.prompts) == 2
    assert "dates_preserved" in llm.prompts[1]


# --------------------------------------------------------------------------- #
# Failing twice falls back to the baseline
# --------------------------------------------------------------------------- #
def test_fails_twice_and_falls_back_to_the_baseline(tmp_path):
    llm = ScriptedLLM(PTA_DROPPED_DATE, PTA_DROPPED_DATE)
    result = run_pipeline(llm, PTA_NOTICE, log_path=tmp_path / "log.jsonl")
    assert result.status == "fallback_extractive"
    assert result.summary == result.baseline.summary


# --------------------------------------------------------------------------- #
# An API error falls back and is logged
# --------------------------------------------------------------------------- #
def test_api_error_falls_back_and_is_logged(tmp_path):
    log_path = tmp_path / "log.jsonl"
    llm = ScriptedLLM(RuntimeError("the model is unavailable"))
    result = run_pipeline(llm, PTA_NOTICE, log_path=log_path)
    assert result.status == "fallback_extractive"
    assert "RuntimeError" in result.error
    assert "api_error" in [record["event"] for record in _log_lines(log_path)]


# --------------------------------------------------------------------------- #
# An invalid notice is rejected
# --------------------------------------------------------------------------- #
def test_invalid_notice_is_rejected():
    with pytest.raises(InvalidNoticeError):
        run_pipeline(None, "Come to school.")


# --------------------------------------------------------------------------- #
# A user override is applied and logged
# --------------------------------------------------------------------------- #
def test_override_is_applied_and_logged(tmp_path):
    log_path = tmp_path / "log.jsonl"
    result = run_pipeline(None, PTA_NOTICE, log_path=log_path)
    edited = "PTA meeting on 8 December 2026. Please bring your receipt booklet."

    overridden = apply_override(result, PTA_NOTICE, edited, log_path=log_path)

    assert overridden.status == "user_override"
    assert overridden.overridden is True
    assert overridden.summary == edited
    event = next(r for r in _log_lines(log_path) if r["event"] == "override")
    assert "passed" in event["details"]


# --------------------------------------------------------------------------- #
# The log file is valid JSON lines
# --------------------------------------------------------------------------- #
def test_log_file_is_valid_json_lines(tmp_path):
    log_path = tmp_path / "log.jsonl"
    run_pipeline(ScriptedLLM(PTA_DROPPED_DATE, PTA_DROPPED_DATE), PTA_NOTICE, log_path=log_path)

    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]
    assert lines
    for line in lines:
        record = json.loads(line)
        assert set(record) == {"timestamp", "notice_hash", "event", "details"}
