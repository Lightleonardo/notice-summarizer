# Evaluation

`evaluate.py` runs every notice in `samples/` through the extractive
baseline (and, when a real API key is set, the AI path) and records:

- **Words in/out** and the **reduction** percentage
- **Fact recall**: the share of the notice's dates, times, amounts, and
  contacts that survive into the summary (normalised comparison)
- **Validation**: whether the summary passes the accuracy checklist

Regenerate with `python evaluate.py`.

## Extractive baseline (no model)

| Sample | Words in | Words out | Reduction | Fact recall | Validation |
| --- | ---: | ---: | ---: | ---: | :---: |
| 01_pta_meeting.txt | 75 | 56 | 25% | 5/5 (100%) | pass |
| 02_date_range.txt | 44 | 40 | 9% | 4/4 (100%) | pass |
| 03_amounts_times.txt | 51 | 46 | 10% | 5/5 (100%) | pass |
| 04_prohibition.txt | 55 | 37 | 33% | 1/1 (100%) | pass |
| 05_wrong_weekday.txt | 58 | 45 | 22% | 3/3 (100%) | pass |
| 06_vague.txt | 22 | 15 | 32% | n/a | pass |
| 07_informational.txt | 46 | 30 | 35% | 2/2 (100%) | pass |

Across all samples: mean reduction **24%**, fact recall **20/20 (100%)**, validation passed on **7/7**.

## AI summaries

Not run: no working `OPENAI_API_KEY` is configured. Set one in `.env`
and re-run `python evaluate.py` to fill this table with real model
summaries. We do not fabricate model results; any simulated run would be
labelled as *simulated*.

## Why fact recall, and not a text-overlap score like ROUGE

ROUGE-style scores measure the overlap of words or n-grams between two
pieces of text. That rewards *fluent wording*, but it cannot tell you that
"3 December" became "4 December": a single character changes the meaning
while the overlap barely moves. The whole point of this tool is to protect
the facts a parent acts on - the date, the time, the amount, the contact -
so we measure exactly those. **Fact recall** asks: of the dates, times,
amounts, and contacts in the notice, how many are still present in the
summary? A dropped or altered fact drops the score immediately, which is the
failure mode we care about.

Two honest caveats:

- Recall says nothing about fluency, and it cannot judge whether an
  instruction still *means* the same thing after rewriting. It checks
  presence, not faithfulness of wording - see `docs/decisions.md`.
- The extractor has a known limit (`27/11` with no year is not recognised),
  so a summary that abbreviates a date that way is counted as a dropped
  fact. That is a false alarm in the safe direction.

Preservation beats brevity: the baseline never drops a fact sentence to hit
the word budget, which is why it keeps 100% recall at the cost of a modest
reduction.
