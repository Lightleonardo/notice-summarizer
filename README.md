# School Notice Summarizer

Turn a school notice into a short, parent-friendly summary — with a fact check
that catches dropped or invented dates, times, amounts, and contacts.

Two summaries are produced side by side:

- a **rule-based extractive baseline** that can only copy sentences out of the
  notice, so it never invents a fact;
- an **AI summary** that reads better and is much shorter, but is only accepted
  when it passes the validator. If it fails, the pipeline retries once and then
  falls back to the baseline.

A rule-based **checklist** also judges the *input* notice (audience, date, action,
next step, weekday consistency), and the user can always edit the final text.

## How it works

1. The notice is cleaned and validated (not empty, 5–3000 words).
2. A checklist flags anything vague or inconsistent in the input notice.
3. The extractive baseline keeps every fact-bearing sentence.
4. If a model is configured, it drafts a structured summary
   (`headline`, `summary`, `key_dates`, `actions`).
5. The validator compares the AI summary to the notice, fact by fact. On failure
   it retries once with the failure text, then falls back to the baseline.
6. The user can edit and override; the override is validated and logged.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and fill in your key:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=        # optional: custom/proxy endpoint
```

Without a key the app still works — it uses the extractive baseline only.

## Run the app

```powershell
streamlit run app.py
```

## Run the tests

```powershell
pytest
```

## Evaluation

`python evaluate.py` writes `docs/evaluation.md`: words in/out, reduction, fact
recall, and validation results for every sample. On the bundled samples the
baseline keeps 100% of facts (20/20) at an average 24% reduction. We report fact
recall rather than a text-overlap score like ROUGE, because ROUGE rewards fluent
wording but cannot tell that "3 December" became "4 December" — see the rationale
in [docs/evaluation.md](docs/evaluation.md).

## Demo

<!-- Add the screen recording / GIF link here. -->

## Privacy

Only send **approved, synthetic, or anonymised** text to a third-party API. Real
notices can contain children's names and personal contact details. The bundled
samples are entirely synthetic. Failure logs store only a short hash of the
notice, never the notice text.

## Project layout

| Path | What it is |
| --- | --- |
| `app.py` | Streamlit demo (thin; all logic lives in `notice_tool`) |
| `notice_tool/ingest.py` | Upload → clean text |
| `notice_tool/text.py` | Normalise text, split sentences |
| `notice_tool/facts.py` | Extract dates, times, money, phones, emails, URLs |
| `notice_tool/baseline.py` | Extractive summary |
| `notice_tool/checklist.py` | Rule-based check of the input notice |
| `notice_tool/validator.py` | Accuracy checklist: summary vs notice |
| `notice_tool/llm_summarizer.py` | Prompt + structured output schema |
| `notice_tool/pipeline.py` | Orchestration, retry, fallback, logging, override |
| `evaluate.py` | Runs the samples and writes `docs/evaluation.md` |
| `samples/` | Synthetic notices (+ `ground_truth.md`) |
| `tests/` | pytest suite |
| `docs/decisions.md` | The reasoning behind the choices |
| `docs/evaluation.md` | Generated evaluation report |
| `logs/` | Runtime failure logs (gitignored) |

## Key decisions

Short version; the full reasoning is in [docs/decisions.md](docs/decisions.md).

- **Both approaches, deliberately.** The baseline is safe but only somewhat
  shorter; the AI summary is shorter but risky. The baseline is the fallback, and
  the AI summary has to pass validation to be shown.
- **Validate facts, normalised.** We compare re-extracted facts, not raw strings,
  so a faithful reformatting passes while a lost or altered fact fails.
- **Bare "N" money rule.** `N500` and `N5,000` count as naira; `N1` and `N2` are
  ignored as likely class names.
- **Dates are day-first.** `24/11/2026` means 24 November.
- **One retry, then fallback.** A single correction prompt, then the safe
  baseline.
- **Users can override, and overrides are logged** with whether they passed.
- **Limitations.** The validator checks that facts are present, not that the
  wording is faithful; negation checking is a rough heuristic. Validators reduce
  risk, they do not remove it.
