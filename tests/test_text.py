"""Tests for notice_tool.text — sentence splitting."""

from notice_tool.text import normalize, split_sentences


def test_protects_am_pm():
    assert split_sentences("School begins at 8 a.m. sharp. Please be early.") == [
        "School begins at 8 a.m. sharp.",
        "Please be early.",
    ]


def test_protects_titles():
    assert split_sentences("Call Mrs. Adeyemi today. She will help.") == [
        "Call Mrs. Adeyemi today.",
        "She will help.",
    ]


def test_protects_month_abbreviations():
    assert split_sentences("The exam is on 24 Nov. 2026 for all pupils.") == [
        "The exam is on 24 Nov. 2026 for all pupils.",
    ]


def test_splits_on_line_breaks():
    assert split_sentences("Dear Parents\nPlease come") == [
        "Dear Parents",
        "Please come",
    ]


def test_splits_on_bullets():
    assert split_sentences("Bring:\n- your receipt\n- a pen\n") == [
        "Bring:",
        "your receipt",
        "a pen",
    ]


def test_known_limit_sentence_ending_in_am_is_not_split():
    # Known limit: a sentence ending in "a.m." is kept with the next one. This is
    # safe for preservation (we keep more text, never less).
    assert split_sentences("School opens at 8:00 a.m. Please arrive early.") == [
        "School opens at 8:00 a.m. Please arrive early.",
    ]


def test_normalize_fixes_line_endings_and_collapses_spaces():
    assert normalize("a\r\nb\r\nc") == "a\nb\nc"
    assert normalize("a   b\tc") == "a b c"
