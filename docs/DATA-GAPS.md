# Data gaps found by the owner's audit

Source: the owner's read-only gap audit, shared 2 Nov 2026 as a 77,087-row CSV
(`lexbharat_data_gaps_consolidated.csv`, about 15 MB, held in the owner's artifact, not in
this repo). Every figure here is **Reported** — read out of that CSV, not re-run here. The
audit's own provenance (which snapshot, which export, when) is **not verified**.

## Rows by gap type

| gap_type | rows |
|---|---|
| acts_garbled_sections | 45,963 |
| sections_chapter_gaps | 8,530 |
| acts_missing_sections | 6,814 |
| regulators_no_source_link | 4,107 |
| judgments_no_text_supreme_court | 4,068 |
| acts_stub_or_empty | 3,716 |
| hand_copied_india_code | 1,990 |
| judgments_no_text_high_courts (**1,000-row sample of 16,024,412**) | 1,000 |
| court_year_zero_rows | 897 |
| laws_missing_2025_2026 | 2 |

## 1. State Acts exist, across 36 states and union territories

The audit holds **8,517 distinct state Act ids** (`IND_state_*`) with at least one gap, and
the `state` column carries **36** distinct values — andhra-pradesh through west-bengal,
including the union territories. Only Acts *with a gap* appear in this file, so the real
number of state Acts is higher.

**This corrects a working assumption.** `core/coverage.json` currently names Central Acts
only. That was set conservatively because the *working copy on the Mac* holds 74,484 Central
Act points — but what the copy took and what the dataset holds are different questions, and
the coverage statement is about the dataset. The original PRD wording ("central and state
Acts and regulations") may well have been right.

**It does not settle O7.** The count still has to be run (Part 1 on the originals), because
this file proves existence, not usable coverage.

### Traps the count must handle, or it will overstate

| Trap | Rows | Effect if ignored |
|---|---|---|
| `central_act_copy_filed_under_state` | 130 | A central Act counted again under a state. The sample is the IT Act 2000 filed under tamil-nadu, flagged as the same title as central `IND_central_1999` |
| `possible_state_act_filed_as_central` | 47 | The reverse |
| `fuller_copy_exists_elsewhere` | 93 | The same Act counted twice, once as a stub |
| `zero_numbered_sections` | 1,230 | An Act counted as covered that has no sections to serve |
| `far_below_expected` | 2,215 | An Act counted as covered that is mostly missing |
| Ids prefixed `IND_REP_` | 710 | Repealed Acts counted as live coverage. The name carries the marker, e.g. "(Rep., Act 44 of 2023)" |

**An Act with no usable sections must not be counted as covered.** "We hold 22,264 Acts" and
"we hold N Acts you can actually read" are different claims, and only the second belongs on
the coverage page (O7).

## 2. High Courts may not be buildable from this data at all

The audit says the High Court export is **metadata only**: `no_judgment_text_loaded (High
Court export is metadata only)` and `High Court export has no text column`, across
**16,024,412 cases** and **26 courts**.

If that holds for the data we would actually serve, PRD-v2 section 4.3's plan to add Bombay,
Telangana and Kerala after the launch gate **cannot be delivered as written**:

- No judgment text means nothing to retrieve beyond metadata.
- Verifier check 3 (quoted words appear in the record) can never run.
- Check 2 (the record exists) would still pass, so a citation could carry a tick while
  pointing at a record with no readable text. That is the tick meaning less than it says.

**Not verified, and it matters which is true.** This describes an *export*. Whether
`legal_corpus_v1` / `legal_corpus_v2` hold High Court chunks *with text* is a different
question and is exactly what the Part 6 inventory should answer before the drive is ejected.
Do not re-plan the roadmap on this line alone; do not promise High Courts until it is settled.

## 3. Things that touch the verifier and the tick

- **4,068 Supreme Court judgments with no text** (`no_opening_preview_and_no_text_in_app`).
  If any of these is retrievable, check 2 passes and check 3 has nothing to match. Confirm
  they are absent from the served collection rather than assuming it.
- **45,963 garbled sections**: amendment markers (`Subs.`, `Ins.`, `Omitted`, `Rep. by`) sit
  inside the section text. Two risks: a quote fails check 3 because of the marker noise, or
  the model quotes an amendment note as though it were the operative law.
- **4,107 regulator records with no source URL.** The tick promises the link goes to the
  record's `pdf_url` / `source_url`. Where there is none, the interface must not imply one.

## 4. The snapshot boundary is real

`laws_missing_2025_2026`: **zero Acts for 2026, central and state.** Whatever the data-as-of
date says, there is nothing recent in here. This supports showing the date everywhere and
promising no currency.

## What to do with this

1. The Part 1 Acts count (running on the originals) applies the dedupe and usability rules in
   section 1 above, and feeds `core/coverage.json`.
2. The Part 6 inventory settles whether High Court text exists anywhere in the collections.
3. The trust lane confirms no-text records cannot reach a user with a tick.
4. Nothing here is promoted above **Reported** until re-run against the data we serve.
