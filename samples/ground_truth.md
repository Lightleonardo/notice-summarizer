# Sample notices — ground truth

All notices below are **synthetic** and contain no real names, children's names, or
real phone numbers. Phone numbers use clearly fictitious groupings (0803 123 4567,
0805 987 6543) and emails use `example.org`.

This file records, for each sample, the facts a *good* summary must keep. It is the
ground truth used to sanity-check the baseline and the validator.

---

## 01_pta_meeting.txt — normal notice (date, time, amount, phone, email)

**Must keep**
- Date: **8 December 2026** (Tuesday — weekday is correct)
- Time: **10:00 a.m.**
- Amount: **₦2,000** per family (voluntary contribution)
- Phone: **0803 123 4567**
- Email: **pta@example.org**
- Action: **bring your receipt booklet**; attend the PTA meeting on 8 December

**Trap:** a single notice carrying one of every fact type (date + time + amount +
phone + email).

---

## 02_date_range.txt — date range

**Must keep**
- Date range: **from 7 to 18 December 2026** (both endpoints: 7 Dec and 18 Dec)
- Time: papers start each day at **9:00 a.m.**
- Time: arrival by **8:30 a.m.**
- Date: report cards issued on **18 December 2026**
- Action: ensure wards arrive on time

**Trap:** a range ("from 7 to 18 December") that must not collapse to a single date.

---

## 03_amounts_times.txt — several amounts and times, mixed formats

**Must keep**
- Amount: **₦8,500** (Primary fees) — symbol form
- Amount: **N8,500** (Nursery fees) — bare-N form
- Amount: **₦3,000** (bus service)
- Time: school begins at **7:30 a.m.**
- Time: school closes at **2.30 PM**
- Date: payment must be made before **5 December 2026**
- Action: pay fees before the deadline

**Trap:** several amounts and times written in different formats
(`₦8,500`, `N8,500`, `7:30 a.m.`, `2.30 PM`) that must all survive.

---

## 04_prohibition.txt — prohibition

**Must keep**
- Prohibition: **do not send children with phones** / students are **not allowed**
  to bring mobile phones or electronic gadgets
- Consequence: phones will be **confiscated** and returned at end of term
- Date: rule takes effect **Monday, 7 December 2026** (weekday is correct)

**Trap:** a negation. A summary must keep a negation, not flip it into a permission.

---

## 05_wrong_weekday.txt — wrong weekday (deliberate trap)

**Must keep**
- Date: **24 November 2026**
- Time: **11:00 a.m.**
- Phone: **0805 987 6543**
- Action: confirm attendance by calling the front office

**Trap:** the notice says **"Monday, 24 November 2026"**, but
`datetime.date(2026, 11, 24)` is a **Tuesday**. The weekday/date check must flag the
mismatch. (Nothing here should be "auto-corrected" — the check only warns.)

---

## 06_vague.txt — vague notice (no date, no contact)

**Must keep**
- Action: a request to **come to school soon** to talk about the child

**Traps / expected checklist output**
- **No exact date** — "soon" is relative → `date` check should be `weak`
- **No date, time, amount, or contact** at all → a summary cannot invent any
- **No next step** (no contact, no "reply"/"submit") → `next step` check `missing`
- Audience is present ("Dear Parents")

---

## 07_informational.txt — informational, no action

**Must keep**
- Time: library open **8:00 a.m. to 3:00 p.m.** every weekday
- Fact: new reference books and storybooks added
- Fact: **no fee** for library use

**Trap:** informational only — there is **no action to take**. A good summary should
not fabricate a task.
