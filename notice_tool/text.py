"""Text clean-up and safe sentence splitting.

Splitting has to be careful: a naive split on "." would break ``8 a.m.``,
``Mrs.``, ``24 Nov.``, and so on. We therefore shield the full stop of a small
set of well-known abbreviations before splitting, then restore it afterwards.

Known limit (documented in docs/decisions.md): when a sentence *ends* in an
abbreviation such as ``a.m.`` we cannot tell the full stop apart from the
abbreviation dot, so we keep it joined with the following sentence. That errs
on the safe side because the baseline summary then keeps more text, never less.
"""

from __future__ import annotations

import re

# A placeholder that can never appear in real notice text.
_SENTINEL = "\x00"

# Leading bullet / numbered-list markers, e.g. "- ", "* ", "1. ", "2) ".
_BULLET = re.compile(r"^\s*(?:[-*\u2022\u2013]|\d+[.)])\s*")

# Full stops that belong to an abbreviation rather than a sentence end.
_ABBREV = re.compile(
    r"(?<![A-Za-z])"
    r"(?:a\.m|p\.m|Mr|Mrs|Ms|Dr|Prof|Rev|Sr|Jr|St|No|etc"
    r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\.",
    re.IGNORECASE,
)

# A real sentence boundary: punctuation followed by whitespace.
_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def normalize(text: str) -> str:
    """Tidy raw text: unify line endings and collapse runs of spaces/tabs."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"[ \t]+", " ", text)


def _split_line(line: str) -> list[str]:
    """Split a single line into sentences, protecting abbreviations."""
    protected = _ABBREV.sub(lambda m: m.group(0)[:-1] + _SENTINEL, line)
    return [
        part.replace(_SENTINEL, ".").strip()
        for part in _BOUNDARY.split(protected)
        if part.strip()
    ]


def split_sentences(text: str) -> list[str]:
    """Return the sentences of ``text`` in order.

    Line breaks and leading bullets also start a new sentence, so headings and
    list items come through as separate entries.
    """
    sentences: list[str] = []
    for raw_line in normalize(text).split("\n"):
        line = _BULLET.sub("", raw_line.strip())
        if line:
            sentences.extend(_split_line(line))
    return sentences
