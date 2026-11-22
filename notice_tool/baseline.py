"""Extractive baseline summariser.

No model involved: we simply keep the sentences that carry a fact (a date,
time, amount, phone, email or link) or that tell parents what to do, and drop
the rest. The opening sentence is added back when the word budget allows.

Guiding rule: *preservation beats brevity.* We never drop a sentence that holds
a fact just to hit the word budget - we flag ``over_budget`` instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from notice_tool.facts import extract_facts
from notice_tool.text import split_sentences

# Soft word budget for a read-at-a-glance summary.
WORD_BUDGET = 60

_INSTRUCTION = re.compile(
    r"\b(bring|come|pay|attend|reply|confirm|submit|contact|call|email|"
    r"collect|register|ensure|arrive|note|sign|return|send|complete|"
    r"do not|must|should|required|requested|invited|compulsory)\b",
    re.IGNORECASE,
)


@dataclass
class BaselineSummary:
    """An extractive summary plus the numbers a caller may want to report."""

    summary: str
    original_words: int
    summary_words: int
    reduction: float
    over_budget: bool


def _has_fact(sentence: str) -> bool:
    facts = extract_facts(sentence)
    return bool(
        facts.dates or facts.times or facts.money
        or facts.phones or facts.emails or facts.urls
    )


def _is_important(sentence: str) -> bool:
    return _has_fact(sentence) or bool(_INSTRUCTION.search(sentence))


def baseline_summary(text: str) -> BaselineSummary:
    """Produce an extractive summary of ``text``."""
    sentences = split_sentences(text)
    original_words = len(text.split())

    kept = [sentence for sentence in sentences if _is_important(sentence)]

    # Keep the opening line ("Dear Parents...") when it fits the budget.
    if sentences:
        opening = sentences[0]
        if opening not in kept:
            used = sum(len(sentence.split()) for sentence in kept)
            if used + len(opening.split()) <= WORD_BUDGET:
                kept.insert(0, opening)

    summary = " ".join(kept)
    summary_words = len(summary.split())
    reduction = 0.0 if original_words == 0 else 1.0 - summary_words / original_words

    return BaselineSummary(
        summary=summary,
        original_words=original_words,
        summary_words=summary_words,
        reduction=reduction,
        over_budget=summary_words > WORD_BUDGET,
    )
