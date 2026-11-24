"""Tests for evaluate.py.

We test the two pieces of logic the evaluation report depends on: the fact-recall
measure and the markdown it is rendered into. The AI path is skipped when no key
is configured, so these tests never touch the network.
"""

from pathlib import Path

import evaluate

SAMPLES = sorted(Path("samples").glob("*.txt"))


# --------------------------------------------------------------------------- #
# Fact recall
# --------------------------------------------------------------------------- #
def test_recall_counts_every_fact_type():
    source = (
        "Exam on 3 December 2026 at 9:00 a.m. The fee is \u20a68,500. "
        "Call 080-3123-4567 or email a@example.org."
    )
    summary = (
        "Exam 3 December 2026, 9:00 a.m. Fee \u20a68,500. "
        "Call 080-3123-4567, email a@example.org."
    )
    preserved, total = evaluate.fact_recall(source, summary)
    assert (preserved, total) == (5, 5)


def test_recall_flags_a_dropped_fact():
    source = "Meet on 3 December 2026 at 9:00 a.m."
    summary = "Meet on 3 December 2026."
    preserved, total = evaluate.fact_recall(source, summary)
    assert preserved == 1
    assert total == 2


def test_recall_returns_none_when_there_are_no_facts():
    assert evaluate.fact_recall("Come to school soon.", "Bring a pencil.") is None


def test_baseline_keeps_every_fact_on_every_sample():
    for path in SAMPLES:
        text = path.read_text(encoding="utf-8")
        summary = evaluate.baseline_summary(text).summary
        recall = evaluate.fact_recall(text, summary)
        if recall is not None:
            preserved, total = recall
            assert preserved == total, (path.name, preserved, total)


# --------------------------------------------------------------------------- #
# Markdown
# --------------------------------------------------------------------------- #
def test_markdown_has_a_row_per_sample():
    rows = evaluate.evaluate_baseline(SAMPLES)
    doc = evaluate.render_markdown(rows, ai_available=False)
    for path in SAMPLES:
        assert path.name in doc
    assert "Fact recall" in doc
    assert "Why fact recall" in doc
