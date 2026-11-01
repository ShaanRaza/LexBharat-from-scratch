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

## 5. Court names are not canonical — a filter on one spelling misses most of a court

**Measured** from the Part 3 tally over 2,760,000 consecutive `legal_corpus_v2` points
(a uniform slice, about 26% of the scan), 2 Nov 2026. `court` holds **38 distinct values**,
and several courts appear under more than one of them:

| Court | Values seen | Counts in the slice |
|---|---|---|
| Rajasthan | `High Court Of Rajasthan` / `High Court of Rajasthan` | 316,091 / 453 |
| Bombay | `Bombay High Court` / `High Court of Bombay` | 32,084 / 183 |
| Patna | `Patna High Court` / `High Court of Patna` | 27,874 / 307 |
| Orissa | `Orissa High Court` / `High Court of Orissa` | 116,837 / 127 |
| Madras | `Madras High Court` / `High Court of Madras` | 32,139 / 89 |
| Calcutta | `Calcutta High Court` / `High Court of Calcutta` | 225 / 4 |
| Gauhati | `Gauhati High Court` / `High Court of Gauhati` | 6,555 / 63 |
| Allahabad | `Allahabad High Court` / `High Court of Allahabad` | 772 / 1 |

Also: **`High Court  for State of Telangana` carries two spaces** after "Court". Telangana is
one of the three courts named for phase 2 (PRD-v2 section 4.3), so a filter written from the
obvious spelling returns nothing at all.

**Rules that follow:**

- Never filter a court by a single literal. Normalise case and whitespace and merge known
  variants, in one shared place, the way coverage categories live in one file (A51).
- Never report a per-court count without merging variants first. Allahabad reads as 772 or
  as 1 depending on which spelling you pick.
- **`Supreme Court of India` has no variant** — checked against all 38 values for any
  casing, whitespace, "Hon'ble" or abbreviation form. So the copy's exact-match filter is
  not skipping Supreme Court points on account of the name (**Checked**, 2 Nov 2026).

### The unnamed points are still open

**17,815 points in the slice (0.65%) have no usable `court`** — the tally cannot separate a
missing field, a null and the literal string "None". An exact-match filter misses all of
them, and a verification pass built on the same filter would not notice. The Supreme Court
rate in the slice is 3.1%, so most of these are probably not Supreme Court, but that is weak
evidence, not proof. Resolved by the parquet cross-check in section 6.

## 6. Verify completeness against an independent source, not the same filter

The copy selects Supreme Court chunks with `court = "Supreme Court of India"`. Checking that
copy by re-enumerating the originals **with the same filter** cannot detect a point the
filter never matched — it is the same question asked twice.

So the primary completeness check is a **parquet cross-check**: compare every English
Supreme Court `chunk_id` in the legislation/judgment parquet against the `chunk_id` values in
`kanoon_v1`, both directions, with duplicate detection. The parquet is an independent oracle,
it needs no `court` filter, it names the exact missing chunks rather than a count, and it
reads local files instead of re-scanning 11.8M points.

**An oracle is only independent if its own selection is.** If Set A is picked with an exact
match on the parquet's own `court` column, and that column carries the same spelling variants
as Qdrant's, then both sides are wrong in the same way and agree with each other. So Set A is
defined twice — once from the parquet's court/language columns, and once structurally from
`_INSC_` in `case_id` — and any disagreement between the two definitions is itself a finding.
The same applies to "English": if the parquet's language column is as sparse as Qdrant's
`language_code`, "English Supreme Court chunks" is not a well-defined set, and translated
chunks mixed into Set A would show up as false "missing" alarms.

Known target: the parquet holds **371,247** English Supreme Court chunks against **371,159**
under the exact filter (**Reported**, from earlier notes). That 88-chunk difference is either
unnamed-court points, or something else; the cross-check names them either way.

## 7. The source dataset card, and three conflicts with what we believed

Source: the HuggingFace card for `vaquill/open-india-law`, read 2 Nov 2026. **Dataset card**
evidence label throughout. The dataset is gated (free, but you accept conditions first);
snapshot `v2026.08`, 54 GB, CC BY 4.0, Apache-2.0 for the scrapers.

### What it says it holds

| Content | Volume | Period |
|---|---:|---|
| Court judgments | 12,848,644 documents | 1950–2025 |
| Tribunal and regulator matters | 813,168 | 1985–2026 |
| Enactments | 22,265 | 1806–2026 |
| Sections of legislation | 1,098,577 | |

Courts: **the Supreme Court plus all 25 High Courts.** District and trial courts are
excluded. Legislation covers Central plus all states and union territories, from India Code.
Judgments are one row per chunk; group by `case_id`, order by `chunk_index`.

### Conflict 1 — the collection table does not match what is on the drive

The card's table:

| Collection | Points | Card says it holds |
|---|---:|---|
| `legal_corpus_v1` | 19,595,718 | High Court and Supreme Court judgment chunks |
| `legal_corpus_v2` | 11,823,753 | **Tribunal and regulator chunks** |
| `acts_india` | 1,098,577 | Legislation and regulatory provisions |

**Observed on the drive (Measured, Part 3 tally over 2.76M points of v2):** v2 is about 96%
High Court and 3.1% Supreme Court, across 38 court names. No tribunals.

The card is very likely wrong here, and its own text says why: tribunal material **has no text
layer** and is indexed by case only — roughly 2.1M PDFs awaiting OCR. Material with no text
cannot be 11.8 million text chunks. So `v1` and `v2` are both judgment collections
(19.6M + 11.8M ≈ the 32.5M total), split some other way.

**What follows:** nobody has looked at `legal_corpus_v1` yet. If it holds Supreme Court chunks
too, the copy — which reads only v2 — is incomplete. The parquet cross-check would catch
that, because the parquet is an independent oracle, but v1 should be checked directly.

### Conflict 2 — the card says English only; our working figure says ~742,000 vernacular chunks

The card: *"the only language tag is English. The page does not mention translations."*

Our notes carry ~742,000 vernacular Supreme Court chunks, and the Set A plan expects
A-minus-B to be roughly that size. Both cannot be right. Possibilities: the parquet carries
untagged vernacular rows the card does not describe; the audit's language classification was
wrong; or the two are counting different things.

**Do not treat ~742,000 as the expected difference.** Let the script classification report
what is actually there — that is exactly what it is for.

### Conflict 3 — "metadata only" is about tribunals, not High Courts

The owner's gap audit reported the High Court export as metadata only (section 2 above). The
card says the opposite for judgments — extracting clean text from court PDFs is described as
the project's main contribution — and says *tribunal* material is the part without text.

**This is the likelier reading, and it is good news: High Courts have text, so phase 2 is
real.** It also means the "no text" risk moves to tribunals, which are already "Later" in
PRD-v2 section 4.3 and now carry a known OCR cost. Still **not verified** against the drive:
settle it by opening one High Court point, which the Part 6 inventory does.

### Other facts worth carrying

- **Not current law.** One-off snapshots, no refresh schedule; refreshes depend on community
  adoption of the scrapers. Corrections arrive as superseding snapshots, never in-place edits.
  This supports decision D2 and the data-as-of date on every page.
- **Embeddings:** voyage-4, 1024 dimensions, cosine, with a named sparse vector for BM25
  hybrid search. Queries must use the same model. Matches what the copy carries (**Measured**:
  1,024-d dense, ~190–230 non-zero sparse terms).
- **Redactions already applied at source:** names of victims' relatives and protected children,
  phone numbers, emails, and PAN, IFSC and Aadhaar numbers in identifying context. Judgments a
  court ordered unpublished, including in-camera matters, are excluded. Useful for the privacy
  page, but it is the source's claim, not our verification.
- **Attribution is a licence condition**, not a courtesy — imposed by the eCourts and
  NCLT/NCLAT policies. `Data: Open India Law by Vaquill AI, CC BY 4.0` stays on every page.
- **The card contradicts itself on totals** (32,572,660 judgment chunks against 32,518,048
  vectors; 1,098,577 sections against 1,098,269 provisions) and says so. The 308-row gap we
  already owed an explanation for is visible in the card itself.
