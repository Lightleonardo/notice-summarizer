"""Evaluation.

Runs every notice in ``samples/`` through the extractive baseline - and, when a
real ``OPENAI_API_KEY`` is configured, through the AI path - then writes a report
to ``docs/evaluation.md``:

* words in, words out, and the reduction percentage
* **fact recall**: the share of the notice's dates, times, amounts, and contacts
  that survive into the summary (compared normalised, not as raw strings)
* whether the accuracy validator passed

Run it with:

    python evaluate.py

Without a key the AI table is simply reported as "not run" - we never fabricate
model results, and any simulated run would be labelled as simulated.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from notice_tool.baseline import baseline_summary
from notice_tool.facts import extract_facts
from notice_tool.pipeline import run_pipeline
from notice_tool.validator import validate_summary

SAMPLES_DIR = Path("samples")
OUT_PATH = Path("docs") / "evaluation.md"


# --------------------------------------------------------------------------- #
# Fact recall
# --------------------------------------------------------------------------- #
def fact_recall(source: str, summary: str) -> tuple[int, int] | None:
    """Return ``(preserved, total)`` facts shared by notice and summary.

    Facts are grouped as dates, times, amounts, and contacts (phones, emails and
    URLs together). Returns ``None`` when the notice holds no facts at all.
    """
    notice = extract_facts(source)
    got = extract_facts(summary)
    groups = [
        (notice.dates, got.dates),
        (notice.times, got.times),
        (notice.money, got.money),
        (notice.phones | notice.emails | notice.urls, got.phones | got.emails | got.urls),
    ]
    total = sum(len(expected) for expected, _ in groups)
    if total == 0:
        return None
    preserved = sum(len(expected & actual) for expected, actual in groups)
    return preserved, total


# --------------------------------------------------------------------------- #
# Rows
# --------------------------------------------------------------------------- #
@dataclass
class Row:
    """One line of the report: the numbers for a single notice."""

    name: str
    status: str
    words_in: int
    words_out: int
    reduction: float
    preserved: int
    total: int
    passed: bool


def _recall_cell(row: Row) -> str:
    if row.total == 0:
        return "n/a"
    return f"{row.preserved}/{row.total} ({row.preserved / row.total:.0%})"


def evaluate_baseline(samples: list[Path]) -> list[Row]:
    """Run the extractive baseline over ``samples``."""
    rows: list[Row] = []
    for path in samples:
        text = path.read_text(encoding="utf-8")
        base = baseline_summary(text)
        preserved, total = fact_recall(text, base.summary) or (0, 0)
        rows.append(
            Row(
                name=path.name,
                status="extractive_only",
                words_in=base.original_words,
                words_out=base.summary_words,
                reduction=base.reduction,
                preserved=preserved,
                total=total,
                passed=validate_summary(base.summary, text).passed,
            )
        )
    return rows


def evaluate_ai(samples: list[Path], llm) -> list[Row]:
    """Run the full pipeline (real model) over ``samples``."""
    rows: list[Row] = []
    for path in samples:
        text = path.read_text(encoding="utf-8")
        result = run_pipeline(llm, text)
        preserved, total = fact_recall(text, result.summary) or (0, 0)
        rows.append(
            Row(
                name=path.name,
                status=result.status,
                words_in=len(text.split()),
                words_out=len(result.summary.split()),
                reduction=result.baseline.reduction,
                preserved=preserved,
                total=total,
                passed=result.validation.passed,
            )
        )
    return rows


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _overall(rows: list[Row]) -> str:
    preserved = sum(r.preserved for r in rows)
    total = sum(r.total for r in rows)
    mean_reduction = sum(r.reduction for r in rows) / len(rows) if rows else 0.0
    recall = f"{preserved}/{total} ({preserved / total:.0%})" if total else "n/a"
    passed = sum(1 for r in rows if r.passed)
    return (
        f"Across all samples: mean reduction **{mean_reduction:.0%}**, fact recall "
        f"**{recall}**, validation passed on **{passed}/{len(rows)}**."
    )


def render_markdown(rows: list[Row], *, ai_rows: list[Row] | None = None, ai_available: bool) -> str:
    """Render the full evaluation report."""
    lines = [
        "# Evaluation",
        "",
        "`evaluate.py` runs every notice in `samples/` through the extractive",
        "baseline (and, when a real API key is set, the AI path) and records:",
        "",
        "- **Words in/out** and the **reduction** percentage",
        "- **Fact recall**: the share of the notice's dates, times, amounts, and",
        "  contacts that survive into the summary (normalised comparison)",
        "- **Validation**: whether the summary passes the accuracy checklist",
        "",
        "Regenerate with `python evaluate.py`.",
        "",
        "## Extractive baseline (no model)",
        "",
        "| Sample | Words in | Words out | Reduction | Fact recall | Validation |",
        "| --- | ---: | ---: | ---: | ---: | :---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row.name} | {row.words_in} | {row.words_out} | {row.reduction:.0%} "
            f"| {_recall_cell(row)} | {'pass' if row.passed else 'fail'} |"
        )
    lines += ["", _overall(rows), ""]

    lines += ["## AI summaries", ""]
    if not ai_available or ai_rows is None:
        lines += [
            "Not run: no working `OPENAI_API_KEY` is configured. Set one in `.env`",
            "and re-run `python evaluate.py` to fill this table with real model",
            "summaries. We do not fabricate model results; any simulated run would be",
            "labelled as *simulated*.",
        ]
    else:
        lines += [
            "Real model summaries (not simulated):",
            "",
            "| Sample | Status | Words out | Fact recall | Validation |",
            "| --- | --- | ---: | ---: | :---: |",
        ]
        for row in ai_rows:
            lines.append(
                f"| {row.name} | {row.status} | {row.words_out} "
                f"| {_recall_cell(row)} | {'pass' if row.passed else 'fail'} |"
            )

    lines += [
        "",
        "## Why fact recall, and not a text-overlap score like ROUGE",
        "",
        "ROUGE-style scores measure the overlap of words or n-grams between two",
        "pieces of text. That rewards *fluent wording*, but it cannot tell you that",
        "\"3 December\" became \"4 December\": a single character changes the meaning",
        "while the overlap barely moves. The whole point of this tool is to protect",
        "the facts a parent acts on - the date, the time, the amount, the contact -",
        "so we measure exactly those. **Fact recall** asks: of the dates, times,",
        "amounts, and contacts in the notice, how many are still present in the",
        "summary? A dropped or altered fact drops the score immediately, which is the",
        "failure mode we care about.",
        "",
        "Two honest caveats:",
        "",
        "- Recall says nothing about fluency, and it cannot judge whether an",
        "  instruction still *means* the same thing after rewriting. It checks",
        "  presence, not faithfulness of wording - see `docs/decisions.md`.",
        "- The extractor has a known limit (`27/11` with no year is not recognised),",
        "  so a summary that abbreviates a date that way is counted as a dropped",
        "  fact. That is a false alarm in the safe direction.",
        "",
        "Preservation beats brevity: the baseline never drops a fact sentence to hit",
        "the word budget, which is why it keeps 100% recall at the cost of a modest",
        "reduction.",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Model (only when a real key is configured)
# --------------------------------------------------------------------------- #
def _load_llm():
    """Return a chat model when a real key is set, else ``None``.

    Mirrors ``app.get_llm`` so the CLI and the app agree on what counts as a
    configured model.
    """
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key.startswith("sk-your"):
        return None

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )


def main() -> None:
    samples = sorted(SAMPLES_DIR.glob("*.txt"))
    rows = evaluate_baseline(samples)

    llm = _load_llm()
    ai_rows = evaluate_ai(samples, llm) if llm is not None else None

    doc = render_markdown(rows, ai_rows=ai_rows, ai_available=llm is not None)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(doc, encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
