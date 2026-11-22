# Decisions

Running notes on the choices behind the tool, with the reasoning. (Expanded in
Step 12.)

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
bare `03:00`. (This was caught by a test during Step 3 — see the time test for
"8:00 a.m. to 3:00 p.m.".)
