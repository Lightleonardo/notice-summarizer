# Decisions

Running notes on the choices behind the tool, with the reasoning. The README
gives the short version; this file has the detail.

## Two approaches, on purpose

A notice can be summarised with rules, with a model, or - as here - with both.
We ship both, because each covers the other's weakness.

- The **extractive baseline** can only copy sentences out of the notice, so it
  never invents a fact. That safety costs brevity: it keeps every fact-bearing
  sentence verbatim, so it is only *somewhat* shorter. On our samples it keeps
  100% of facts at an average 24% reduction (see `docs/evaluation.md`).
- The **AI summary** is much shorter and reads far better, but it can drop,
  change, or invent a fact - and a wrong date or amount is exactly what a parent
  cannot afford to miss.

So the baseline is the safety net, and the AI summary is the polished output that
has to earn its place by passing the validator. If it cannot, we fall back to the
baseline.

## Validate facts, and compare them normalised

We do not trust the model's summary; we check it. The validator re-extracts the
facts from the notice and from the summary and compares them. If a date, time,
amount, or contact is missing, changed, or invented, the summary fails.

We compare **normalised** facts, not raw strings. "3 December", "Dec 3rd", and
"3/12/2026" are the same fact, as are "₦8,500", "N8,500", and "8,500 naira".
Normalising first (dates to a `(month, day)` pair, times to a 24-hour string,
money to a `(currency, amount)` pair, phones to ten digits) means a summary is not
punished for merely *reformatting* a fact - only for losing or altering it. A
raw-string diff would do the opposite: it would fail a faithful rewrite and, worse,
pass a subtly wrong fact that happens to share characters.

## Money: the bare-"N" rule

A bare `N` before a number is ambiguous. In Nigerian school notices `N500`
almost always means ₦500, but `N2` is just as likely to be a class name
("Class N2 has 30 pupils", "Nursery N2 and N1"). Guessing wrong in either
direction is bad: read a class name as money and the validator invents a fact;
read ₦500 as a class and the validator flags a real amount as dropped.

The rule we settled on:

* **Unambiguous markers accept any amount** — the `₦` symbol and the `NGN`
  code always mean naira, even for tiny amounts (`₦50` is accepted).
* **A bare `N` only counts as naira when the number is unmistakably an amount** —
  it must have a thousands comma (`N5,000`, `N15,000`, `N8,500`) or at least
  three digits (`N500`). So `N2` and `N1` are ignored.

Class names in these notices are single digits (`N1`, `N2`), so the three-digit
floor separates the two worlds cleanly. `$` and `£` map to `USD` and `GBP`; the
word `naira` after a number also maps to `NGN`.

## Dates: day-first for numeric dates

`24/11/2026` and `24.11.2026` are read **day first** (day 24, month 11 →
`(11, 24)`), matching how dates are written in the notices this tool targets.
This is an assumption, and it is a stated one: a notice that meant month-first
would be misread. Day-first is the documented convention here.

## Dates: dd/mm without a year is a known limit

`27/11` (day/month, no year) is **not** recognised as a date. It is not a full
date, and treating a bare `27/11` as "27 November" risks colliding with other
number pairs (scores, room numbers). The consequence is a *false alarm*: if a
summary abbreviates a real date down to `27/11`, the validator reports the date
as dropped even though a human would understand it. For a tool whose job is to
protect dates, erring toward flagging is the safe direction.

## Times: am/pm wins over the 24-hour reading

A time written with an am/pm marker (`3:00 p.m.`) is owned by the 12-hour
parser, so the 24-hour parser deliberately skips it rather than also emitting a
bare `03:00`. A test caught this — see the time test for "8:00 a.m. to 3:00 p.m."

## One retry, then fall back

If the first AI summary fails validation, we retry once, and the retry prompt
carries the validator's failure text (for example "missing dates: (12, 3)") so the
model has a concrete thing to fix. One retry is the sweet spot: a single clear
correction message fixes most formatting slips, while looping would multiply
latency and cost for a summary that may simply be beyond the model. If the second
attempt still fails - or the API errors - we fall back to the baseline, which we
know is faithful. Every failure is logged, never hidden.

## Users can override, and overrides are logged

The validator is a check, not a gatekeeper. The user always gets the last word:
they can edit the final text and use their version. We do run the validator on
that edited text and log the override together with whether it passed. That keeps
the human in control while preserving a record of *when* someone overrode a failed
check - useful for spotting a validator that is too strict, or a model that keeps
missing the same thing.

## Limitations

- The validator checks that facts are **present**, not that the wording is
  faithful. It cannot tell that a rewritten instruction now means something
  different.
- Prohibition checking is a rough heuristic: it looks for any negation word, so a
  negation used for something else can fool it.
- The extractors have known limits (the dd/mm-without-year false alarm above, and
  a number that directly abuts an amount can be misread as a phone). These are
  documented rather than hidden.
- **Validators reduce risk, they do not remove it.** A summary that passes the
  checks is very likely faithful - not guaranteed faithful.
