"""Tests for notice_tool.baseline — extractive summary (Step 4)."""

from pathlib import Path

from notice_tool import baseline
from notice_tool.facts import extract_facts

SAMPLES = sorted(Path("samples").glob("*.txt"))


def test_keeps_fact_sentences_and_drops_fluff():
    result = baseline.baseline_summary(
        "Dear Parents. The meeting is on 8 December 2026. Thank you."
    )
    assert "8 December 2026" in result.summary
    assert "Thank you" not in result.summary


def test_adds_opening_sentence_when_budget_allows():
    result = baseline.baseline_summary("Dear Parents. The meeting is on 8 December 2026.")
    assert result.summary.startswith("Dear Parents")


def test_preserves_original_order():
    result = baseline.baseline_summary(
        "A: 8 December 2026. Random filler sentence here. B: pay ₦2,000 now."
    )
    assert result.summary.index("8 December") < result.summary.index("2,000")


def test_reports_reduction_and_budget():
    result = baseline.baseline_summary(
        "Dear Parents. " + "filler words here. " * 20 + "The meeting is on 8 December 2026."
    )
    assert 0.0 <= result.reduction < 1.0
    assert isinstance(result.over_budget, bool)
    assert result.original_words > result.summary_words


def test_baseline_never_loses_a_fact_on_any_sample():
    for path in SAMPLES:
        text = path.read_text(encoding="utf-8")
        summary = baseline.baseline_summary(text).summary
        notice, kept = extract_facts(text), extract_facts(summary)
        assert notice.dates <= kept.dates, path.name
        assert notice.times <= kept.times, path.name
        assert notice.money <= kept.money, path.name
        assert notice.phones <= kept.phones, path.name
        assert notice.emails <= kept.emails, path.name
