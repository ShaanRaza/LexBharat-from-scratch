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
| judgments_no_text_high_courts (**1,000-row sample of 16,024,412**; see section 2: High Court points in the served collections carry text) | 1,000 |
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

## 2. High Courts are buildable: the "metadata only" reading is WRONG for the data we serve

**Settled 4 Nov 2026 (Measured).** The audit reported `no_judgment_text_loaded (High Court export is metadata only)` and
`High Court export has no text column`, across 16,024,412 cases and 26 courts, and this section used to say High Courts
"may not be buildable from this data at all". That reading does not hold for `legal_corpus_v1` / `legal_corpus_v2`, the
collections the product is built from. Evidence, all read from the originals (read-only):

- **One High Court point opened from each of three courts**, text field populated in all three:

  | Court | Collection | Chunk | Text field |
  |---|---|---|---|
  | Kerala | `legal_corpus_v2` | `KLHC010546832023_021` | 4,208 characters; opens "Case: Bail Appl./6428/2023 ... Court: High Court of Kerala ... RESPONDENT/COMPLAINANT: ..." |
  | Bombay | `legal_corpus_v1` | `HCBM030119402018_000` | 2,554 characters; opens "Case: CA/4715/2018 ... Court: Bombay High Court ... Section: PARAGRAPH" |
  | Telangana | `legal_corpus_v1` | `HBHC010353512013_000` | 1,152 characters; opens "Case: WP/6535/2013 ... WRIT PETITION No.6535 of 2013" |

- **Not an anecdote: 59,454 points**, drawn at random from all 30 court prefixes of both collections (1,100 of them Supreme Court,
  the rest High Court) for the embedding health check (section 21), **have zero empty text fields and none under 200 characters.**
- **Text exists at scale and was already spent on**: A141 counted 3,422M tokens of High Court text in the 2,865,144 whole
  cases the index lacks (`A141-COST-PICTURE.md` section 2, exact local token count), and A123 re-embedded 217,766 Kerala chunks
  from their stored text (reproduced at cosine 0.998 or better before the run).
- Verifier check 3 (quoted words appear in the record) therefore can run on High Court passages, and a High Court citation's
  tick points at readable text.

**What the audit's line was really describing** is the *export* it examined (and tribunal material, section 7 Conflict 3). It
is not a property of the served collections. Of the remaining gap: High Court cases that have **no chunk in any collection**
are an indexing problem, not a text problem (section 19; A141 prices loading them). **Not verified:** the audit's 1,000-row
sample of High Court cases with no text (the `judgments_no_text_high_courts` row above) was not reproduced; it may describe
rows in the parquet that carry no text, which is a different population from the points sampled here.

## 3. Things that touch the verifier and the tick

- **4,068 Supreme Court judgments with no text** (`no_opening_preview_and_no_text_in_app`).
  If any of these is retrievable, check 2 passes and check 3 has nothing to match. Confirm
  they are absent from the served collection rather than assuming it.
  **Resolved 4 Nov 2026 (SC lane, Measured; A-SC1, §23 below): 4,068 = 2,739 served + 1,329
  unserved.** The 2,739 are served WITH text (smallest 160 words, median 4,580), so the audit's
  "no text" label is wrong for them. The 1,329 have no point in `kanoon_v1` (record_missing if
  cited). No served chunk anywhere has an empty body.
- **45,963 garbled sections**: amendment markers (`Subs.`, `Ins.`, `Omitted`, `Rep. by`) sit
  inside the section text. Two risks: a quote fails check 3 because of the marker noise, or
  the model quotes an amendment note as though it were the operative law.
- **4,107 regulator records with no source URL.** The tick promises the link goes to the
  record's `pdf_url` / `source_url`. Where there is none, the interface must not imply one.
- **Text that is in the record but is not the court's holding** (a party's argument, a rejected argument, a lower court's holding): 5 of 79 cited pairs in a real-model run. No check can see it. Section 22. Check 3 fires on only 6% of cited pairs; section 25.

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
**Settled in section 2, 4 Nov 2026:** a High Court point was opened from each of three courts and the text is there.

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

## 8. The parquet cross-check: the copy is clean, the source is not

**Measured**, 2 Nov 2026, by the parquet cross-check (section 6's design). Set A was taken
structurally from `_INSC_` in `case_id` with no language filter; Set B three ways (`court`,
`_INSC_`, both) which all gave the same number. Scripts were read from the chunk text, never
from a label.

### The copy is complete relative to the original

The original `legal_corpus_v2` and `kanoon_v1` both hold **371,159** Supreme Court points, by
`court` and by `court_type` alike, and `legal_corpus_v1` holds **0**. Nothing was lost in the
copy, and v1 adds nothing. The copy is also **100% Latin-script** across all 371,159 — no
vernacular chunk was pulled in by the court-only filter, which had been an assumption until now.

### What the parquet holds that the vectors do not

The parquet carries **1,113,313** Supreme Court chunks over 37,014 cases, with
`language_code` 100% filled across 16 languages (English 371,247, Hindi 307,509, Punjabi
306,477). Against the copy:

| Difference | Chunks | Cases |
|---|---:|---:|
| In the parquet, **not in any Qdrant collection** — all English | **10,112** | 749 (734 wholly absent) |
| In Qdrant, not in the parquet | 5,153 | 92 |
| **Duplicate `chunk_id`s**, each on two points, in the original as well as the copy | **4,871** | 392 |

371,247 − 10,112 + 5,153 + 4,871 = 371,159. The earlier 88-point near-match was a coincidence
of three larger differences, not an explanation. Named lists are in `~/qdrant-kanoon/reports/`.

**The 749 absent cases cluster in recent years** — 300 from 2021, 235 from 2019. They cannot be
retrieved at all, so the product cannot answer on them however the question is asked. That is a
coverage hole in the dataset's own vectors, not in our copy, and it belongs on the coverage page
rather than in a footnote.

### The duplicates reach the answer, so they are the more urgent of the two

4,871 chunk ids sit on two points each. Nobody asked about these, and they matter more than the
missing chunks:

- The same passage can occupy two of the eight slots the gate allows (step 7), spending
  retrieval capacity on text already present.
- Worse, the two copies get **different source ids**, so an answer can carry `[S1]` and `[S4]`
  pointing at identical text. Every verifier check passes — the records exist, the quotes match,
  the passages were retrieved — and the reader sees two authorities where there is one.

Nothing in §5's four checks is designed to catch that, because nothing is wrong with either
citation taken alone.

**Fix in the pipeline, not in the data:** drop duplicates after search and before the gate,
on `chunk_id` first and a text hash second. It costs nothing, needs no re-embedding, and does
not touch the originals.

### Drive speed, measured at last

LAWSSD reads at **35.5 MB/s** (2 GiB via `dd`, twice, 60.55 s and 60.47 s, no cache effect).
All 26 judgment files in full would be about 25 minutes. Column-only reads take seconds.

### What this evidence does not cover

The absence of the 749 cases rests on `case_id` and `court`. A chunk filed under a different
`case_id` would not show. And 148,810 chunks in the difference could not be classified: 53,332
mixed-script, and 95,478 Latin-script but labelled Hindi or Punjabi, where `text` equals
`text_original`. Four were inspected by hand and were an English header followed by OCR noise
from scanned pages; the rest are **not verified**. None of them are in the copy.

## 9. About half of the ORIGINAL `acts_india` has wrong keyword vectors (the served collections do not)

**Read this first (corrected 4 Nov 2026).** Every percentage and count in this section, the 26.6%, the 49.4%, the 19,835, the
504,600 and the 524,400, describes the **original `acts_india`** on the original instance, which **nothing serves**. They were read
as though they described live keyword search; they do not. Where each stands today:

| Collection | Instance | Serves users? | Wrong sparse vectors | Evidence |
|---|---|---|---|---|
| `acts_india` (original, 1,098,577 points) | 6333 | **No** | **Yes**: 19,835 of 74,509 Central (26.6%, full scan); about 504,600 of 1,024,068 non-central (49.4% of a 10,000 sample). Untouched, by rule | **Measured** 2 Nov 2026 |
| `kanoon_v1` (455,755 points: 381,271 Supreme Court, 74,484 Central Acts) | 7333 | **Yes** | **None**: 0 of 74,484 Central Acts would change (full check, 3 Nov); 0 of 3,072 sampled today | **Measured** |
| `acts_noncentral_v1` (1,024,068 state and regulator Acts) | 7333 | **No** (staging, A133) | **None**: 510,366 were repaired on the way in; 0 of 20,000 random points differ from a fresh encoding (4 Nov); 0 of 3,072 sampled again later on 4 Nov | **Measured** |

So live keyword search is not affected, and the state and regulator Acts that are repaired are not yet served at all (promotion sizing: DECISIONS
A145, `docs/COSTS.md` section 2d). The 25-point difference between 74,509 and 74,484 Central points is the dedupe, not a repair gap. `data/sparse_fix.py`
no longer runs against `acts_india`: it refuses any original and requires `--collection` naming a copy.

The text below is the original 2 Nov finding, kept as written; read "`acts_india`" in it as the unserved original.

**Measured**, 2 Nov 2026, from `acts_sample_v1`: 10,000 points sampled with a fixed seed
across 90 strata from the 1,024,093 `acts_india` points outside the copy. 200 of 200 checked
field by field match the originals, so the sample itself is sound.

Recomputing the BM25 sparse vectors with FastEmbed gives **49.4% mismatches** (4,944 of
10,000) — regulatory 52.6%, state 45.8%. Every mismatch holds integer-only values, which are
raw term counts rather than BM25 weights: the same signature as the 19,835 Central Act
failures already known.

Extrapolated: about **504,600** mismatching points outside the copy (95% CI 494,800–514,300),
plus the 19,835 measured exactly, so roughly **524,400 of 1,098,577 — about 48% of all Acts
provisions**. The estimate covers the 50 strata with 30 or more sampled points (99.9% of the
population); 40 small strata (1,276 points) are too thin to estimate.

**What it means for a user.** Keyword search is the half of hybrid search that finds exact
things — a section number, an Act by name. That is the main way anyone uses Act lookup. For
roughly half of all provisions, that half of the search is working from the wrong vector.

Everything else in the sample is sound: no empty text, every dense vector 1024-d and unit
norm with no zeros or NaNs, section numbers present on 95%+ of points. Garbled text
(replacement characters) appears in 5.4% of the regulatory sample and 1.6% of the state
sample; how much of that text is unreadable was not measured.

### The repair works — measured on the sample, 2 Nov 2026

`data/sparse_fix.py`, hard-limited to `acts_sample_v1`, re-encoded all 4,944 broken vectors in
about 3 seconds, backing them up first and leaving dense vectors untouched. Ground truth: the
78 sample points whose text contains every query word, 39 of them with broken vectors.

| | Broken points found in top 100 | Unbroken points found |
|---|---:|---:|
| Before repair | **0 of 39** | 39 of 39 |
| After repair | **39 of 39** | 39 of 39 |

Nothing previously found was lost. Top-10 hits rose from 36 to 45. A concrete case: "land
acquisition compensation" now returns The Land Acquisition Act 1894 first; before the repair
it returned a municipal corporations Act and a flood-relief Act.

So this is not a marginal gain — for a broken point, keyword search was finding **nothing**.

**How far to trust it:** 10,000 points, 5 lookups, a lexical stand-in for relevance, recall
measured rather than precision, and encode-and-write speed untested at 524,400 points. It
justifies running the repair; it does not price it.

**Priority — settled 3 Nov 2026.** The 19,830 Central Act points in `kanoon_v1` are **already repaired** (verified read-only: 0 of 74,484 would change; `COSTS.md` §2b). The other ~504,600 sit in the original `acts_india`, which **nothing serves** — only Central Acts are in the copy. **Do not repair them now:** it would mean writing to an original for no present benefit, and §17's rule exists precisely to keep originals untouched. **Instead, the repair belongs in whatever copies them.** Any job that builds a serving collection containing state Acts or regulators must recompute their BM25 sparse vectors on the way in, and say in its report how many it fixed. If that step is skipped, roughly half of those provisions reach users with keyword search finding **nothing** for them — which is how they were found in the first place.

**Built and run, 4 Nov 2026 (DECISIONS A133).** `data/repair_act_sparse.py` copied the 1,024,068 non-central Acts out of the
original (read-only) into the staging collection `acts_noncentral_v1` on the copy instance with every broken sparse vector
re-encoded: **510,366 repaired (49.8%)**, inside the estimate above. Checked: 0 of 20,000 random points differ from a fresh BM25
encoding; dense vectors equal the original's; the original is untouched. On a 5,000-point rehearsal, 193 broken points asked a
keyword question from their own words were found in the top 100 in **0 of 193 before and 184 of 193 after**. Nothing is
promoted into a served collection; that, and the cost of tripling `kanoon_v1`'s points, is the owner's call.

(Superseded note: this section previously said to test on `acts_sample_v1` first — that test is the table above.)

The original guidance stood: test on `acts_sample_v1` — that collection is disposable, already measured, and gives a
before-and-after on real keyword lookups.

## 10. Identical text across different provisions is legitimate, so text-hash dedup is unsafe

The Part 5 sample found **26 groups of points sharing identical text** (52 points). In Acts
this is expected rather than anomalous: short title clauses, repealed-section placeholders and
definitions repeat verbatim across state adaptations of the same central Act.

That breaks the text-hash half of the step 5 deduplication (A71). Dropping the lower-scoring
copy of two genuinely different provisions means citing the wrong Act — the text is the same,
but `act_id`, the citation and the source URL are not.

**Rule:** deduplicate on text **only when both passages come from the same source document** —
the same `case_id` for a judgment, the same `act_id` for a provision. Identical text from two
different documents is two different authorities and both must survive. Deduplication on
`record_id` (the chunk id) is unaffected: that remains a true duplicate wherever it appears,
and it is what the 4,871 measured duplicates actually are.

## 11. The collections were built with DIFFERENT embedding models, and the config has the wrong one

**Measured**, 2 Nov 2026, by re-embedding stored text and comparing to the stored vector
(build step 0's check 1, finally answered):

| Group | Model that reproduces the stored vector | Cosine |
|---|---|---|
| `legal_corpus_v2` Supreme Court chunks | **`voyage-4-large`** (document input) | 0.9987–0.9995 |
| the same chunks under `voyage-4` | not it | 0.94–0.96 |
| `legal_corpus_v1` High Court control | **`voyage-4`** | 0.999984 |

**`core/settings.py:47` says `VOYAGE_EMBED_MODEL = "voyage-4"`, a single global value.** So as
the code stands, a Supreme Court search would embed the query with `voyage-4` against a corpus
built with `voyage-4-large`.

**That failure is silent, which is what makes it serious.** At 0.94–0.96 the two models agree
enough that results come back looking entirely plausible — ranked, relevant-ish, nothing
erroring — while being systematically worse than they should be. With no retrieval-quality
metric in place (CLAUDE.md flags that gap), nobody would have caught it. The first real search
in build step 1 would have been quietly wrong.

The HuggingFace card says the corpus uses "voyage-4 embeddings (1024 dimensions)". For the
Supreme Court chunks that is **wrong**, which is the third card claim to fail against the data.

**What follows:**

1. `VOYAGE_EMBED_MODEL` must become **per collection**, not global — TECH-STACK-v2 section 10
   listed this as "value pending"; it now has measured values, and they differ.
2. **`acts_india` has not been checked.** An earlier note observed one Central Act chunk
   matching `voyage-4-large`. It is a third group and needs the same test before any Act search
   is trusted.
3. Queries must be embedded with the model that built the collection being searched. A hybrid
   query spanning two collections built with different models needs two query embeddings.
4. Cost: `voyage-4-large` is dearer per token, but a query is ~20 tokens, so for search the
   difference is negligible. It matters only for bulk embedding.

### The residual 0.999 is still unexplained

Ruled out by measurement: int8 quantization (stored vectors hold ~700 distinct values; int8
allows at most 256, and none are float16-exact), non-determinism (repeat runs give 1.000000),
ten text variants (strip, trailing newline, NFC, NFKC, carriage returns, control characters,
line and paragraph breaks — a trailing newline moves cosine by only 0.0001–0.0009), and
`voyage-context-4` (0.69–0.88). What remains: an earlier snapshot of `voyage-4-large`, or a
text difference at build time that has not been found.

## 12. Three embedding models are mixed WITHIN collections, by document batch

Section 11 said the model differs per collection. **That was wrong, and the truth is worse.**
111 stored chunks re-embedded across every group (**Measured**, 2 Nov 2026):

| Group | Chunks | `voyage-4` | `voyage-4-large` | `voyage-4-lite` |
|---|---:|---:|---:|---:|
| `legal_corpus_v2` Supreme Court | 23 | 0 | **23** | 0 |
| `acts_india` Central | 7 | 0 | **7** | 0 |
| `acts_india` state | 37 | 24 | 13 | 0 |
| `acts_india` regulatory | 26 | 24 | 2 | 0 |
| `legal_corpus_v1` High Court | 8 | 5 | 2 (Delhi, Patna) | 1 (Allahabad) |
| `legal_corpus_v2` High Court | 10 | 6 | 0 | 4 (Karnataka, Rajasthan, Punjab & Haryana) |

The model follows the **document or ingestion batch**, not the collection — and not even the
court or the state: state Acts split between two models inside a single state, and v2 High
Court Kerala is `voyage-4` while Karnataka is `voyage-4-lite`.

**Two models embedding the same text agree only to about 0.91–0.96 cosine.** So one query
embedding against a mixed collection systematically favours whichever chunks were built with
that model, and penalises the rest. Nothing errors; the ranking is just quietly unfair.

### What is clean, and what this costs

**Clean, and it is exactly what v1 serves:** Supreme Court (23 of 23) and Central Acts
(7 of 7) are homogeneous `voyage-4-large`. All 30 sampled `kanoon_v1` points reproduce under
it. A single query model is correct for the launch corpus.

**Not clean: High Courts, state Acts and regulators.** Serving those with one query model means
a fraction of the corpus ranks fairly and the rest does not.

**So "add all the High Courts" carries a cost nobody had counted.** There is no payload field
recording which model built a chunk, and finding out means re-embedding to compare — which is
the same work as just re-embedding. For 31M High Court chunks at roughly 1,000 tokens each,
voyage-4 at $0.06/M is about **$1,900 one-off** (Estimate; `voyage-4-large` is dearer). That is
on top of the monthly hosting, and it buys a corpus where search is even.

The alternative is serving mixed-model collections and accepting that retrieval quietly
favours part of the data — which, with no retrieval-quality metric in place, nobody would see.

**Open for the owner:** before High Courts or state Acts are served, choose between several
query embeddings (needs a per-chunk model field that does not exist), one chosen model and
accepted unfairness, or re-embedding. Recorded as A120.

## 13. Measured: per-court models cover 92%, and hybrid barely notices a mismatch

**Measured**, 2 Nov 2026. 2,642 chunks across 77 court groups, up to 50 per court from different
cases and random id ranges, re-embedded and compared at cosine 0.998. Per-court tables and raw
cosines: `~/qdrant-kanoon/reports/hc_model_report.md`, `hc_model_results.json`.

This **supersedes section 12's framing** of the cost. The choice is not $1,900 or nothing.

### Is a court one model? Partly

- **`legal_corpus_v1` is mostly single-model per court** (80% of its points). `voyage-4`: Bombay,
  Telangana, Madras, Gujarat, Gauhati, Himachal. `voyage-4-large`: Patna, and Chhattisgarh in
  effect. `voyage-4-lite`: Allahabad, Calcutta, Uttarakhand, Tripura, Sikkim. Mixed: Delhi
  (14/36) and Andhra Pradesh (49/1).
- **`legal_corpus_v2` is internally mixed where it matters** (81% of its High Court points).
  Kerala, Karnataka, Punjab & Haryana, Jharkhand, Himachal, Jammu & Kashmir, Madhya Pradesh,
  Orissa, Manipur, Meghalaya are all mixed. The courts that are single-model in v2 are
  `voyage-4-lite` — and are `voyage-4` or `voyage-4-large` in v1.
- **What drives the mixing is unknown.** It is not the case year: v2 Kerala is mixed in both eras.
- **Volume-weighted:** v1 is 56/14/30 (`voyage-4` / lite / large); v2 is 29/42/28.
- **A per-court-majority config matches about 92% of all 31.0M High Court points** — 98% of v1,
  84% of v2. The remaining 8% would be mismatched.

### Update, 3 Nov 2026: one court holds three models, and the 18% outlier is identified

**Measured.** In a random sample of 50 healthy Kerala v2 chunks (section 17, adapter test), 9 did not
reproduce under `voyage-4` (cosine 0.937 to 0.959). Those same 9 re-embedded under each `voyage-4`-family
model with `input_type: "document"`, 1024 dimensions, the stored text verbatim (35,316 tokens, about Rs 0.2;
`kfix_which_model.py`, `kerala_fix/which_model.json`), cosine to Vaquill's stored vector:

| Model | Chunks reproduced at 0.998 or more | Range over the 9 chunks |
|---|---:|---|
| `voyage-4` | 0 | 0.938 to 0.959 |
| `voyage-4-large` | **4** (0.9992 to 0.9995) | 0.908 to 0.9995 |
| `voyage-4-lite` | **5** (0.9999 to 1.0000) | 0.904 to 1.0000 |

**Every one of the 9 is reproduced by exactly one model, and the other two miss by 0.04 to 0.10.** So none is
unexplained: Kerala v2's healthy chunks are about **82% `voyage-4`, 10% `voyage-4-lite`, 8%
`voyage-4-large`** (41, 5 and 4 of 50; the 41 are those reproducing under `voyage-4` at 0.998 or more). The
earlier 371-chunk sample agrees on the size of the non-`voyage-4` share: 43 of 371 (11.6%, interval about
9% to 15%) were off `voyage-4`, none between 0.90 and 0.998 apart from that group; its split between lite
and large was not measured.

**What this says about the config.** A court is not one model. A config keyed on court, even
"majority model per court", leaves 12 to 18% of a single healthy Kerala sample on the wrong model, and
Kerala is the court the per-court design assumed was single-model (section 12: "v2 High Court Kerala is
`voyage-4`"). Section 12 already found that the model follows the document or ingestion batch, not the
court; this is the first case in which the other models were named. **The config must key on something finer
than the court.** What that is is **not identified**. Free facts from the 371 local chunks (no case has two
sampled chunks, so a per-document pattern could not be tested): the off-`voyage-4` chunks come from shorter
cases (mean 28 chunks per case against 61) and earlier in the case (mean chunk index 9 against 34); there
is no clear year pattern. Both are consistent with ingestion batches and neither is a key. **Done 3 Nov (see "Is the model a free key?" below):** the siblings share a model within a case copy, doubled cases hold two copies on different models, and no payload field identifies the model. Without a key, the options in section 13's cost table
stand, and hybrid, which the retrieval test below shows loses little to a mismatched query model, remains the
mitigation. That test used a single-model corpus; a mixed corpus is still untested.

### Does the mismatch hurt retrieval? Barely, for hybrid

20 `voyage-4` chunks from Bombay v1, 55 queries from their own sentences, against a local copy of
200,020 Bombay points.

| Search | Query model | recall@10 | recall@50 |
|---|---|---:|---:|
| Dense only | `voyage-4` (matching) | 58% | 69% |
| Dense only | `voyage-4-large` | 55% | 65% |
| Dense only | `voyage-4-lite` | 56% | 65% |
| Hybrid | `voyage-4` (matching) | 76% | 87% |
| Hybrid | `voyage-4-large` | 76% | 87% |
| Hybrid | `voyage-4-lite` | 75% | 87% |

Paired per query, a mismatched model cost 2 queries of 55 on dense@50 and **zero on hybrid**. BM25
rescued 10 of 17 dense misses, and 12 of 19 under mismatch. With names and numbers stripped from
the queries, dense@50 falls 62% to 52% while hybrid holds at 81%.

**Not tested here:** a *mixed* corpus, where a matched and a mismatched document compete in one ranking
(done 3 Nov, next subsection). This test shows only that changing the query model does not hurt a corpus
that was *believed* single-model. **How that belief was established:** it was not checked chunk by chunk.
The 200,020 local Bombay points were never classified. "Single-model" came from re-embedding 100 sampled
Bombay v1 chunks (50 per label spelling), all of which reproduced under `voyage-4` (100 of 100). That bounds
the off-model share of Bombay v1 below about 3.6% at 95%, so the corpus could hold a few percent off-model
chunks, and the 20 target chunks were chosen as `voyage-4`-confirmed. Hybrid's numbers here therefore contain
at most a few percent of whatever mixing costs, not 12 to 18%.

### The question-style retest: hybrid does NOT fully absorb the penalty, and the two tests bracket the truth

**Measured** 3 Nov 2026 (`kfix_q_*.py`, `recall_question.json`, `question_vs_sentence_summary.json`), same
corpus (`kerala_recall_eval3`), same 42 off-model targets and 146 `voyage-4` controls, same stored-against-fresh
`voyage-4` swap of the 43 off-model vectors; only the queries change. `voyage-4` / `query` throughout.

**The two query styles are the two ends of a bracket, neither realistic.** *Sentence-style* queries are
sentences lifted from the chunk: every high-IDF token (names, section numbers, quoted wording) is present, so
sparse search does the absorbing. That is the **optimistic bound** on hybrid. *Paraphrase-style* queries are
two questions per target written in other words by a `claude-haiku` subagent that did not know which targets
were off-model, with **no digits, no capitalised names and no 4-word run from the chunk** (a validator of
mine, run after writing). That strips exactly the anchors BM25 lives on: the **pessimistic bound**. A real
lawyer's question ("limitation period for a Section 138 NI Act complaint?") has natural phrasing *and* an anchor,
so it sits between. **Label for the paraphrase arm: a lower bound on hybrid recall, which makes its cost figure
the HIGH end of the range, not the hybrid cost.** (Read "lower bound" on recall, not on cost.)

| Recall (percent) | Sentence: `voyage-4` controls | Sentence: off-model stored to fresh | Fresh minus stored (95% CI) | Gained / lost | Paraphrase: controls | Paraphrase: off-model stored to fresh | Fresh minus stored (95% CI) | Gained / lost |
|---|---:|---|---|---|---:|---|---|---|
| Dense @10 | 44.2 | 36.0 to 42.3 | +6.3 (+1.8, +12.5) | 7 / 0 | 30.6 | 22.2 to 28.4 | +6.2 (-1.2, +14.3) | 7 / 2 |
| Dense @50 | 56.7 | 45.0 to 53.2 | +8.1 (+3.4, +14.0) | 9 / 0 | 44.1 | 40.7 to 45.7 | +4.9 (+1.2, +9.9) | 4 / 0 |
| Sparse @10 | 84.0 | 91.9 to 91.9 | 0 | 0 / 0 | 19.2 | 16.0 to 16.0 | 0 | 0 / 0 |
| Sparse @50 | 89.2 | 96.4 to 96.4 | 0 | 0 / 0 | 26.0 | 30.9 to 30.9 | 0 | 0 / 0 |
| **Hybrid @10** | 78.8 | 83.8 to 85.6 | **+1.8** (0.0, +4.5) | 2 / 0 | 29.2 | 23.5 to 30.9 | **+7.4** (+2.5, +13.4) | **6 / 0** |
| **Hybrid @50** | 88.4 | 95.5 to 95.5 | **0.0** (0.0, 0.0) | 0 / 0 | 40.2 | 38.3 to 40.7 | **+2.5** (0.0, +6.2) | 2 / 0 |

Queries and targets: sentence 111 queries on 42 targets (controls 344 on 146); paraphrase 81 on 42 (281 on
146). Intervals are 95% cluster bootstraps over targets of the fresh-minus-stored difference. "Cost" is that
difference. In the paraphrase arm the 6 hybrid @10 gains had no losses; an exact-binomial 95% upper bound on the
gained share, treating queries as independent, is 15.4 (the sentence arm's equivalent is 6.4, which section 13
above quoted; the cluster bootstrap is the appropriate one and is used here).

**The three invalidation checks.** (1) *Absolute recall on both arms:* neither arm sits at a floor. Paraphrase
hybrid is 29% (@10) and 40% (@50) for controls, dense 31% and 44%; sparse collapses from 84% to 19% at @10,
which is the direct evidence that the anchors are gone. After the swap the off-model targets reach the
controls' level (hybrid @10 30.9 against 29.2, dense @10 28.4 against 30.6), so the swap isolates the model.
Absolute recall is much lower under paraphrase because a question about a boilerplate chunk in a 100,000-chunk
corpus has many acceptable answers; that leaves headroom, not a failed test. (2) *Validator and survivors:* 376
questions written, **14 rejected (3.7%: 13 shared 4-word runs, 1 reused name)**; every target kept at least
one valid question: off-model 42 of 42 (39 with two, 3 with one, 81 questions), controls 146 of 146 (135 with
two, 11 with one, 281 questions). No rewrite round was needed. Words of 5+ letters that also occur in the
chunk: 34 to 37% of question words against 100% for sentence queries; digits in 0% of questions against 65%.
(3) *Sample questions* (off-model targets): "When does a claimed exemption from private forest vesting law
fail because the claimant obtained the tribunal's decision by fraud?"; "Does the general limitation statute
apply to accident compensation applications, or has the special accident law excluded it?"; "Can an accused
who faces several cases registered at one police station obtain bail in each case on common grounds?"
Natural, specific to the subject, and free of anchors.

**Which case this is: a penalty appears. It is not the production number.** Under the optimistic query style
hybrid cost 1.8 points at @10 and 0 at @50; under the pessimistic style it costs **7.4 points at @10 (95%
CI +2.5 to +13.4) and 2.5 at @50 (0.0 to +6.2)**. Neither endpoint is realistic, so **the truth sits between
them and neither arm may be quoted as the hybrid cost.** This does **not** support the earlier statement that
hybrid absorbs the penalty, and it does not close A128 on "accept". Pinning the number down needs a query set
that mixes natural phrasing with real citation anchors, which is advocate work, not generation work, and is
already on the owner's list. Dense alone loses 5 to 8 points in both styles.

**CORRECTED 4 Nov 2026 (A128): the 5.4 and 0.56 figures in this table are WRONG and withdrawn.** They multiply a mismatch share by ONE
per-chunk cost measured on 42 chunks, which assumes every mismatched chunk loses the same amount. It does not: the end-to-end
measurement (section "Measured end to end", below) found the cost is about 3 points for `voyage-4-large` chunks and roughly
zero for `voyage-4-lite` chunks, and 17 of the 25 court codes are lite. The shares (73%, 7.6%) still describe how many chunks sit
off the query's model; they do not give the recall cost. Read the table below as a record of the superseded arithmetic only.

**Corpus-wide Estimates** (share of chunks mismatched times the per-chunk hybrid cost at @10; upper bounds use
the bootstrap upper limits 4.5 and 13.4; shares are the sample-weighted 73% and 7.6% from the court table and
the volume-weighted about 54% and 8%):

| Mismatched share | Optimistic end (sentence) | Pessimistic end (paraphrase) |
|---|---|---|
| One `voyage-4` query model: 73% | 1.3 points (upper 3.3) | 5.4 points (upper 9.8) |
| One `voyage-4` query model: about 54% | 1.0 (upper 2.4) | 4.0 (upper 7.2) |
| Per-court majority query model: 7.6% | 0.14 (upper 0.34) | 0.56 (upper 1.0) |
| Per-court majority query model: about 8% | 0.14 (upper 0.36) | 0.59 (upper 1.1) |

At @50 the same arithmetic gives 0 at the optimistic end and about 1.8 points (upper 4.5) for a single query
model, 0.19 (upper 0.47) for a per-court config, at the pessimistic end. These are share times a per-chunk
cost measured on 42 chunks (9 of them identified as lite or large) with `voyage-4` queries: Estimates, not
measurements. The per-court config cuts the exposure by roughly a factor of ten at either end. *(Withdrawn 4 Nov 2026: that arithmetic assumed a uniform per-chunk cost, which is false; see the correction above.)* Nothing here
proposes or prices a re-embed.

### Two qualifications on the question-style number, and what a six-court re-embed would involve

**Qualification 1: the pessimistic end likely overstates production. This is reasoning, not measurement.**
Controls reach 29% hybrid @10 under paraphrase against about 85% sentence-style. A 7.4-point gain is large on
a 29% base and small on an 85% base, so the headroom a fixed model penalty can take back scales with base
recall, and real queries that carry anchors (a section number, a case name) have less of it. Nothing measured
here puts a number on that; it is why the paraphrase arm is the high end of the range and not the cost.

**Qualification 2: the 7.6% residual is concentrated, and 7.6% is not the number a user faces.** Outside the
court's majority model (v2 groups, 37 to 73 sampled chunks each): Madhya Pradesh 46%, Orissa 42%, Manipur
42%, Jammu and Kashmir 38%, Meghalaya 34%; **everything else 0 to 4%, apart from Uttarakhand** (below). A user
asking a Madhya Pradesh question faces 46%, which at the two ends of the bracket is a hybrid @10 exposure of
about **0.8 to 3.4 points** (share times per-chunk cost; Estimates). Orissa 0.8 to 3.1, Manipur 0.8 to 3.1,
J&K 0.7 to 2.8, Meghalaya 0.6 to 2.5.

**Correction: Uttarakhand's 30% is a v2 group of 1,023 points.** Exact counts by `court` (read-only facets,
`court_facets.json`): Uttarakhand holds **261,025 points in v1, uniformly lite (52 of 52 sampled)**, and
1,023 in v2, where the 30% (11 of 37) was measured. Court-wide that is about **304 outside-majority chunks
of 262,048, 0.1%**, not 30%. The other five courts exist only in v2 (0 in v1), so their shares stand.

**Pricing a targeted re-embed of the six courts (arithmetic only; no embedding call).** Rate: the Kerala
re-embed, $16.36 over 217,766 chunks = $0.0000751 a chunk (`voyage-4`, about 1,246 tokens a chunk; the sample
that gives the shares used short chunks, so real chunks may be longer). Counts are **Qdrant points**, exact
by `court` label, because that is what a re-embed touches; the parquet has other counts (Madhya Pradesh 970,908
rows against 766,920 points, Orissa 872,833 against 501,386, J&K 181,221 against 240,966).

| Court (v2 group) | Qdrant points | Outside majority | Off-majority chunks (95% range) | At the Kerala rate |
|---|---:|---:|---:|---:|
| Madhya Pradesh | 766,920 | 23 of 50 | 352,783 (252,849 to 457,095) | $27 |
| Orissa | 501,386 | 31 of 73 | 212,917 (159,361 to 270,251) | $16 |
| Jammu and Kashmir | 240,966 | 22 of 58 | 91,401 (64,010 to 122,405) | $7 |
| Manipur | 31,643 | 21 of 50 | 13,290 (9,295 to 17,646) | $1 |
| Meghalaya | 22,209 | 17 of 50 | 7,551 (4,983 to 10,626) | $1 |
| Uttarakhand (v2 group only) | 1,023 | 11 of 37 | 304 (179 to 468) | $0 |
| **Total** | **1,564,147** | | **678,247 (490,677 to 878,491)** | **$51 ($37 to $66)** |

The off-majority chunks are **2.2% of Qdrant's 31.42M v1 and v2 points** (1.6 to 2.8%; 2.1% of the parquet's
32.57M rows) and about **27% of the corpus-wide residual** (taken as about 8% of 31.1M High Court points). The
six courts hold 5.0% of the corpus. At the price of each court's *majority* model (lite is a third of the
`voyage-4` rate, large twice it) the total is $46.

**But $51 is not what a targeted re-embed costs, because the minority chunks cannot be found for free.** The
sibling test above shows no key to a point's model, so picking out the 678,247 means embedding them, which is
the work itself. The cheapest way to reach them is to re-embed **every point in the six groups to the court's
majority model**: **1,564,147 points, about $118 at the Kerala rate (Rs 9,988), $109 at majority-model prices**
(`voyage-4` for Madhya Pradesh and Meghalaya, lite for Orissa and Manipur, large for J&K), **13 to 18 times
below option (c)** ($1,500 to $2,100). Points that already match are rewritten unchanged. Duplicated chunks
(Orissa about 8% and Madhya Pradesh about 5% in the sample estimate) already have a matching twin, and J&K's
duplicates are identical copies that A126 would collapse; both effects lower the real count, and neither was
measured here. What it would buy is the exposure above for users of those five courts and about 27% of the
corpus-wide residual. Whether that is worth $109 to $118 is the owner's call; this section does not propose it.

### Measured end to end, 4 Nov 2026: the per-court config does not show a net gain

The exposure figures above (5.4 points under one query model, 0.56 under a per-court config, both now withdrawn) are shares times a per-chunk
cost; the end-to-end eval of A128 (DECISIONS A128, "REOPENED") measured the net effect on 18,399 chunks of 24 courts, 1,185
queries, through the shipped code. **A per-court config fused by RRF against one `voyage-4` vector: hybrid @10 -0.7 (95%
CI -1.9 to +0.4) equal weight, +1.4 (-0.4 to +3.2) weighted by court size; dense @10 -4.0 (-6.3 to -1.6) and +2.2
(-0.9 to +5.2).** The gain exists for courts embedded by `voyage-4-large` (hybrid @10 +3.8) and not for `voyage-4-lite`
courts (-2.5): matching a lite chunk's model does not help, even with no fusion (-1.9 dense @10 with a court filter). The
single-model `voyage-4-large` vector was better than `voyage-4` (post hoc). So the 7.6% residual and the 73% mismatch
figures above describe how many chunks sit off the query's model, not how much recall that costs: for lite-model
chunks, the measured cost of mismatch is about zero.

### Is the model a free key? The sibling test: no payload field, no id, and duplicates only in some courts

**Measured** 3 Nov 2026 (`kfix_sib_*.py`, `kfix_pair_courts.py`; about Rs 0.32 in Voyage tokens plus read-only
fetches from the original; nothing built or written). The question: is the embedding model a per-case or
per-batch property that can be read from data already held, so that a per-court config could become a
per-batch one at zero cost?

**1. Siblings.** For each of the 9 outlier cases and 5 `voyage-4` control cases, up to 3 other chunks were
fetched and their model identified (`voyage-4` first, then lite and large). 22 outlier-case siblings: 8
`voyage-4`, 7 lite, 6 large, 1 dead; 8 of 8 control-case siblings `voyage-4`. **Two outlier cases are
uniform** (`KLHC010013312018` and `KLHC010003072024`: 3 of 3 siblings `voyage-4-large`, and the case holds as
many chunks as its `total_chunks` says). **Six of the nine hold twice as many chunks as `total_chunks`**
(648 against 324, 384 against 192, 34 against 17, 10 against 5, 2 against 1 twice), the whole case loaded
twice, and their siblings are a mix of two models (e.g. `KLHC010524352016`: chunk 1 appears once as
`voyage-4` and once as lite; `KLHC010052842023`: chunk 0 once `voyage-4`, once dead). None of the five
control cases is doubled. No case showed three models. So the model is uniform within a case *copy*, and a
doubled case holds two copies embedded by different models. 9 outlier cases, so this is evidence, not proof.

**2. Duplicates are different-model pairs in some courts and identical in others.** Both copies' vectors
compared (cosine 0.99 or more: one model; 0.90 to 0.99: two models; under 0.5: one dead):

| Court (v2) | Pairs compared | Same model | Different models | One dead |
|---|---:|---:|---:|---:|
| Kerala, 100k slice | 509 | 0 | **211** | **298** |
| Kerala, 200k-point sample | 12 | 0 | 3 | 9 |
| Orissa | 11 | 0 | **11** | 0 |
| Madhya Pradesh | 10 | 0 | **10** | 0 |
| Karnataka | 12 | 8 | 4 | 0 |
| Jharkhand | 12 | 10 | 2 | 0 |
| Himachal Pradesh | 12 | 11 | 1 | 0 |
| Punjab and Haryana, Rajasthan, Jammu and Kashmir | 12 each | **12 each** | 0 | 0 |
| Supreme Court, Andhra Pradesh | 3, 2 | all | 0 | 0 |

(Up to 12 groups per court from the duplicates of section 18; the Kerala slice is all 509 in-slice pairs.)
**In Kerala, Orissa and Madhya Pradesh a duplicate is the same text embedded by two different models**, which
is the mechanism behind the mixing there (those are the courts with 17%, 42% and 46% outside the majority model
in the table above). In Punjab and Haryana, Rajasthan and Jammu and Kashmir the duplicates are identical
vectors, so duplication does **not** explain the mixing there (J&K is 38% outside its majority model with 12 of
12 duplicate pairs identical). The mixing has more than one cause.

**3. Is duplication a key?** In the 371 healthy Kerala sample chunks, 77% of the off-model chunks (33 of 43)
sit in a duplicate group against 13% of the `voyage-4` ones (42 of 328); 10 of the 43 are single copies.
Among single copies 96.6% are `voyage-4` (286 of 296). That is a free, partial signal for Kerala, but it needs
a scan of every `chunk_id`, it is not established for other courts, and **inside a duplicate group it does not
say which copy is which**: both copies have identical payloads (697 of 697 groups, section 18), and the point
id is not derivable from the chunk id (no standard hash of `chunk_id`, md5, sha1, sha256, sha512, blake2b,
uuid3, uuid5 or crc, reproduces any of 200 sampled ids).

**4. No payload field separates the models.** Of the 371 labelled chunks, every one has the same field set apart
from the optional `judges` and `treatment_mentions` (the signatures split 35 off / 279 `voyage-4`, 7 / 44, 1 / 4
with no pattern), the same `pdf_url` host, the same establishment digits in the case id, and no categorical field
separates them (best single test p = 0.03 across about 40 tests, not significant after correction). Numeric
fields give weak and inconsistent signals (AUC 0.40 to 0.53; the off-model chunks sit slightly earlier in
shorter cases, as in section 13 above). There is no `source_url`, source-file or batch field in the payload.

**5. The vector itself is not a reliable key either, in a first and crude test.** A linear classifier on the
stored vector reaches 97% in random folds but only 74% when a whole court is held out (it learns court content),
and inside Kerala, cross-validated by case, 91.6% accuracy against an 88.4% base rate with an AUC of 0.87: it
finds 21 of the 43 off-model chunks (precision 21 of 30). Not usable as a label. A
better-tuned model could do better; that was not tried.

**Verdict: no free per-point key exists in the payload, the id, or (so far) the vector. That kills the
per-BATCH refinement, not the per-COURT config.** Where duplicates exist (Kerala, Orissa, Madhya Pradesh)
they flag *that* two models are present, not which copy is which, so labelling every point by model costs one
embedding per point, the same as re-embedding it. A **per-batch refinement of the residual 7.6%** (the share
still outside a court's majority model) is therefore dead. **The per-court config is untouched and stays
free:** `court` derives from the record id (`CLAUDE.md` section 6; the id prefix agrees with the court in every
parquet row, section 18), and each court's majority model comes from the 46-group sample above. Model-filtered
dense prefetches **by court** need no per-point label, so the step from 73% to 7.6% mismatch costs no
embedding. (Its latency cost inside the <800 ms target is unmeasured.) Nothing here prices or proposes a
re-embed. **Consequence for A126, now amended:** "keep the healthy copy" applies only to the 217,688 Kerala
groups that contain a dead vector, where the detector says which copy is dead. For the 159,942 groups with two
live copies (211 of 211 sampled are different-model pairs) nothing free says which copy is which, so both are
kept, which is the decision recorded in A126 as amended.

### Does an off-`voyage-4` chunk retrieve worse? Dense yes, by about 6 to 8 points; hybrid by almost nothing

**Measured**, 3 Nov 2026, on the copy instance (`kerala_recall_eval3`, the Kerala eval corpus plus the
off-model chunks; scripts `kfix_off_*.py`, results `kerala_fix/recall_offmodel.json`). Queries are
`voyage-4` / `query` throughout, as in the earlier checks.

**The existing eval could not answer this, and why.** Its 849 queries aim at 344 distinct targets: 198 repaired
chunks (fresh `voyage-4` vectors by construction) and 146 healthy controls. Those controls were *chosen* as
chunks that reproduce under `voyage-4` (`kerala_proof.py`: cosine 0.998 or more), and all 146 do. **The eval
contained no off-model target**, so splitting it by model family gives one full group and an empty one.
Step 1 as planned (re-embed all targets, about 1.06M tokens, Rs 6) was unnecessary: the stored cosines already
cover all 146 and the call reproduces them to 0.0002 (section 17), so it was not run.

**What was built instead.** The 43 off-model healthy Kerala chunks from the 371-chunk sample (cosine 0.929 to
0.960 under `voyage-4`: 5 `voyage-4-lite`, 4 `voyage-4-large` among the 9 identified; the rest not
identified) became targets, with queries from the same recipe as the controls (longest sentence, middle
sentence, names and numbers stripped): 111 queries on 42 targets. Total spend about 54,000 tokens, Rs 0.3.

**Comparison with the `voyage-4` controls** (344 queries, 146 targets; 95% cluster bootstrap over targets):

| Recall | `voyage-4` controls | Off-model | Off minus controls | 95% interval |
|---|---:|---:|---:|---|
| Dense @10 | 44.2% | 36.0% | -8.2 | -21.2 to +5.0 |
| Dense @50 | 56.7% | 45.0% | -11.6 | -23.9 to +0.8 |
| Sparse @10 | 84.0% | 91.9% | +7.9 | +0.6 to +15.1 |
| Sparse @50 | 89.2% | 96.4% | +7.2 | +2.0 to +12.2 |
| Hybrid @10 | 78.8% | 83.8% | +5.0 | -5.2 to +15.1 |
| Hybrid @50 | 88.4% | 95.5% | +7.1 | +1.3 to +12.6 |

The group comparison is **confounded**: the off-model chunks come from different cases (shorter, earlier
in the case, section 13 above), and they are *easier* for keyword search (sparse +7 to +8). It shows a
dense deficit in the expected direction that is not significant with 42 targets, and no hybrid deficit.

**The clean test is the within-chunk swap**: the same 42 chunks and 111 queries, only the dense vector
changed, from the stored off-model one to a fresh `voyage-4` document vector:

| | Stored off-model vector | Fresh `voyage-4` vector | Gained / lost (of 111) |
|---|---:|---:|---|
| Dense @10 | 36.0% | 42.3% | 7 / **0** (sign test p = 0.016) |
| Dense @50 | 45.0% | 53.2% | 9 / **0** (p = 0.004) |
| Hybrid @10 | 83.8% | 85.6% | 2 / 0 (not significant) |
| Hybrid @50 | 95.5% | 95.5% | 0 / 0 |
| Sparse | unchanged | unchanged | 0 / 0 |

Exact (non-approximate) dense search gives the same picture (36.0% to 41.4% at 10, 45.9% to 52.3% at 50).
The other groups did not move (the swap touches only those 43 points).

**(Sentence-style queries only. The paraphrase-style retest in "The question-style retest" below shows a hybrid cost of 7.4 points at @10, so read the next paragraph's hybrid figures as the optimistic end of a bracket.)**

**Outcome, stated as measured: neither of the two clean cases.** There **is** a dense penalty for an
off-model chunk, **about 6 points at @10 and 8 at @50**, caused by the model and not by the population
(every changed query moved in one direction). **Hybrid, which is what ships, absorbs nearly all of it:**
2 of 111 queries at @10 (1.8 points, not distinguishable from zero; 95% upper bound about 6.4) and 0 of 111
at @50 (upper bound about 3.3). **Corrected 3 Nov 2026 (the first version of this sentence scaled by Kerala's 12 to 18%, which is the wrong
share for the corpus).** Per-chunk hybrid cost, stored against fresh `voyage-4` vector, **sentence-style
queries**: 1.8 points at @10 (95% upper bound 6.4), 0 at @50 (upper bound 3.3); dense 6.3 and 8.2. The share
of the corpus those costs apply to depends on the query design (end of section 13): **73%** of the sampled
chunks (volume-weighted about 54%) are not `voyage-4`, so under one `voyage-4` query model the corpus-wide
hybrid cost at @10 would be about **1.3 points (upper bound about 4.7)** (about 1.0 and 3.4 volume-weighted),
and 0 at @50 (upper bound about 2.4); dense about 4.6 and 6.0. Under a per-court majority query model the
mismatched share is **7.6%** (volume-weighted about 8%), giving about **0.14 points at @10 (upper bound about
0.5)** and 0 at @50. All **Estimates** (share times per-chunk cost; the per-chunk cost was measured on 9
identified lite and large chunks among the 42, query model `voyage-4`) and, until the question-style retest
is in, **valid for sentence-style queries only**, the best case for keyword search.
The names-and-numbers-stripped queries, where
dense should matter most, show the same: 1 of 28 gained at hybrid @10.

**Limits, plainly.** (1) The queries are sentences lifted from the target chunk, which is the best case for
keyword search (sparse alone finds 84 to 92% at 10). Real questions lean on dense more, so a dense deficit
could cost more there than it does here. This was not measured. (2) 42 targets, one court, one query model.
(3) Which of lite or large each chunk is made no difference to what was measured, and was not separated.
(4) The off-model share was measured only for Kerala v2 (about 12 to 18%); other courts differ (section 13
above).

**WITHDRAWN 4 Nov 2026: what this paragraph said about the per-court config (that it is "load-bearing, not optional") is wrong.**
The end-to-end eval found no measurable hybrid gain from it, dense clearly worse (-4.0), a mismatch cost of about 3 points for
`voyage-4-large` chunks and about zero for `voyage-4-lite` chunks, and 17 of the 25 court codes lite; the per-court design was
DROPPED (DECISIONS A128). The shares and counts below are still true; the conclusion drawn from them is not. The original paragraph
follows as a record. An earlier version of it called the config "unnecessary rather than merely wrong-grained"; that was wrong and is withdrawn. It rested
on two tests whose corpora were almost entirely `voyage-4` (Bombay v1; the Kerala eval) and on sentence-style
queries. The corpus is not like that: **73% of the sampled High Court chunks are not `voyage-4`** (about 54%
volume-weighted), **7 courts show no `voyage-4` chunk at all** in any sampled group (Patna, Chhattisgarh,
Sikkim, Jharkhand, Jammu and Kashmir, Karnataka, Rajasthan), and **1,543 of the 2,640 sampled chunks (58%) sit
in court groups with no `voyage-4` chunk** (see the table below). Under one `voyage-4` query model that mismatch
reaches most of the corpus; a per-court majority query model cuts it to **7.6%** (about 8% volume-weighted). *(That
is the whole job the config does, and at those shares it matters. The dense deficit it avoids is 6 to 8 points
per mismatched chunk (above). Both sentences are WITHDRAWN: the cost of a mismatch is not uniform.)* Whether *hybrid* also depends on it was tested ("The question-style retest", below): it does, at
the pessimistic end of the bracket (7.4 points at @10); the sentence-style numbers (1.8 points) are the **best
case**, because keyword search is doing the absorbing. The decision, and whether any re-embedding is worth it, is the owner's; this
section does not propose one.

### Off-model share by court, and why the dead-vector scan could not have seen it

**Measured** 2 Nov 2026, tabulated 3 Nov. This is the step-3 design, and it had already been run: up to 50
chunks per court group from `legal_corpus_v1` and `v2`, different cases, random id ranges, each stored vector
compared with a fresh `voyage-4` / `document` embedding, then `voyage-4-lite` and `voyage-4-large` for any
chunk that did not reproduce, so every chunk's model is **identified**, not just flagged
(`hc_model_results.json`; 2,642 chunks, 1.4M tokens). It was not re-sampled; no Voyage call was made for this
table. "Reproduces" is cosine 0.99 or more (two chunks at 0.997 to 0.998 sat just under the earlier 0.998
line and are counted as reproduced). 2 of the 2,642 are dead vectors, not off-model, and are excluded.

**Two shares, because they answer different questions.** *Not `voyage-4`* is the mismatch if every court is
queried with `voyage-4`, the model used in sections 13 and 17. *Outside majority* is the mismatch if each court
is queried with its own majority model (the per-court config). Many courts are 100% not `voyage-4` yet
perfectly uniform (all `voyage-4-lite`), so they cost nothing under the per-court config and a great deal
under a single query model.

| Court | Coll | Prefix | Healthy chunks | `voyage-4` | lite | large | Not `voyage-4` (95% interval) | Majority model | Outside majority |
|---|---|---|---:|---:|---:|---:|---|---|---:|
| Allahabad | v1 | UPHC | 100 | 0 | 100 | 0 | **100%** (96 to 100) | lite | 0% |
| Calcutta | v1 | WBCHCA | 58 | 0 | 58 | 0 | **100%** (94 to 100) | lite | 0% |
| Calcutta | v1 | WBCHCJ | 1* | 0 | 1 | 0 | **100%** (21 to 100) | lite | 0% |
| Calcutta | v1 | WBCHCO | 49 | 0 | 49 | 0 | **100%** (93 to 100) | lite | 0% |
| Chhattisgarh | v1 | CGHC | 55 | 0 | 0 | 55 | **100%** (93 to 100) | large | 0% |
| Patna | v1 | BRHC | 100 | 0 | 0 | 100 | **100%** (96 to 100) | large | 0% |
| Sikkim | v1 | SKHC | 50 | 0 | 50 | 0 | **100%** (93 to 100) | lite | 0% |
| Tripura | v1 | TRHC | 54 | 0 | 54 | 0 | **100%** (93 to 100) | lite | 0% |
| Uttarakhand | v1 | UKHC | 52 | 0 | 52 | 0 | **100%** (93 to 100) | lite | 0% |
| Andhra Pradesh | v1 | APHC | 76 | 1 | 0 | 75 | **99%** (93 to 100) | large | 1% |
| Delhi | v1 | DLHC | 59 | 16 | 0 | 43 | **73%** (60 to 83) | large | 27% |
| for State of Telangana | v1 | HBHC | 67 | 67 | 0 | 0 | **0%** (0 to 5) | voyage-4 | 0% |
| Bombay | v1 | HCBM | 114 | 114 | 0 | 0 | **0%** (0 to 3) | voyage-4 | 0% |
| Gauhati | v1 | GAHC | 102 | 102 | 0 | 0 | **0%** (0 to 4) | voyage-4 | 0% |
| Gujarat | v1 | GJHC | 50 | 50 | 0 | 0 | **0%** (0 to 7) | voyage-4 | 0% |
| Himachal Pradesh | v1 | HPHC | 60 | 60 | 0 | 0 | **0%** (-0 to 6) | voyage-4 | 0% |
| Madras | v1 | HCMA | 95 | 95 | 0 | 0 | **0%** (0 to 4) | voyage-4 | 0% |
| Madras | v1 | HCMD | 17* | 17 | 0 | 0 | **0%** (0 to 18) | voyage-4 | 0% |
| for State of Telangana | v2 | HBHC | 56 | 0 | 56 | 0 | **100%** (94 to 100) | lite | 0% |
| Andhra Pradesh | v2 | APHC | 62 | 0 | 62 | 0 | **100%** (94 to 100) | lite | 0% |
| Bombay | v2 | HCBM | 100 | 0 | 100 | 0 | **100%** (96 to 100) | lite | 0% |
| Calcutta | v2 | WBCHCJ | 11* | 0 | 11 | 0 | **100%** (74 to 100) | lite | 0% |
| Delhi | v2 | DLHC | 55 | 0 | 55 | 0 | **100%** (93 to 100) | lite | 0% |
| Gauhati | v2 | GAHC | 99 | 0 | 99 | 0 | **100%** (96 to 100) | lite | 0% |
| Gujarat | v2 | GJHC | 50 | 0 | 50 | 0 | **100%** (93 to 100) | lite | 0% |
| Himachal Pradesh | v2 | HPHC | 60 | 0 | 16 | 44 | **100%** (94 to 100) | large | 27% |
| Jammu and Kashmir | v2 | JKHC | 58 | 0 | 22 | 36 | **100%** (94 to 100) | large | 38% |
| Jharkhand | v2 | JHHC | 54 | 0 | 10 | 44 | **100%** (93 to 100) | large | 19% |
| Karnataka | v2 | KAHC | 54 | 0 | 4 | 50 | **100%** (93 to 100) | large | 7% |
| Madras | v2 | HCMA | 73 | 0 | 73 | 0 | **100%** (95 to 100) | lite | 0% |
| Madras | v2 | HCMD | 31 | 0 | 31 | 0 | **100%** (89 to 100) | lite | 0% |
| Chhattisgarh | v2 | CGHC | 50 | 0 | 50 | 0 | **100%** (93 to 100) | lite | 0% |
| Rajasthan | v2 | RJHC | 99 | 0 | 99 | 0 | **100%** (96 to 100) | lite | 0% |
| Patna | v2 | BRHC | 98 | 0 | 98 | 0 | **100%** (96 to 100) | lite | 0% |
| Sikkim | v2 | SKHC | 14* | 0 | 14 | 0 | **100%** (78 to 100) | lite | 0% |
| Calcutta | v2 | WBCHCA | 25 | 1 | 24 | 0 | **96%** (80 to 99) | lite | 4% |
| Punjab and Haryana | v2 | PHHC | 69 | 10 | 59 | 0 | **86%** (75 to 92) | lite | 14% |
| Allahabad | v2 | UPHC | 52 | 10 | 42 | 0 | **81%** (68 to 89) | lite | 19% |
| Uttarakhand | v2 | UKHC | 37 | 11 | 26 | 0 | **70%** (54 to 83) | lite | 30% |
| Manipur | v2 | MNHC | 50 | 21 | 29 | 0 | **58%** (44 to 71) | lite | 42% |
| Orissa | v2 | ODHC | 73 | 31 | 42 | 0 | **58%** (46 to 68) | lite | 42% |
| Madhya Pradesh | v2 | MPHC | 50 | 27 | 23 | 0 | **46%** (33 to 60) | voyage-4 | 46% |
| Meghalaya | v2 | MLHC | 50 | 33 | 17 | 0 | **34%** (22 to 48) | voyage-4 | 34% |
| Kerala | v2 | KLHC | 48 | 40 | 5 | 3 | **17%** (9 to 30) | voyage-4 | 17% |
| Calcutta | v2 | WBCHCO | 2* | 2 | 0 | 0 | **0%** (0 to 66) | voyage-4 | 0% |
| Tripura | v2 | TRHC | 1* | 1 | 0 | 0 | **0%** (0 to 79) | voyage-4 | 0% |

*n under 20: read as an anecdote. Shares are of the 2,640 healthy chunks in 46 court groups (a court
label with several spellings or prefixes is split by the id prefix, which agrees with the court in every
parquet row, section 18). Intervals are Wilson 95%.*

**Summary.** Not `voyage-4`: 73% of the sampled chunks overall (v1 55%, v2 87%). Outside the court's own
majority model: 7.6% overall (**v1 1%, 2 of 18 groups; v2 12%, 13 of 28 groups, 11 of them at 10% or
more**: Madhya Pradesh 46%, Orissa 42%, Manipur 42%, Jammu & Kashmir 38%, Meghalaya 34%, Uttarakhand 30% (a 1,023-point v2 group; its 261,025 v1 points are uniformly lite, so court-wide it is 0.1%),
Himachal Pradesh 27%, Delhi v1 27%, Allahabad v2 19%, Jharkhand 19%, Kerala 17%, Punjab and Haryana 14%).
These are sample shares of 50-ish chunks per group, **not volume-weighted**; the volume-weighted estimate
stays the one above (about 92% of all High Court points matched by a per-court majority, 98% of v1, 84% of v2).
Courts such as Bombay v1, Gauhati v1, Madras v1, Gujarat v1 and Telangana v1 are uniformly `voyage-4`; Bombay v2,
Delhi v2, Gujarat v2, Rajasthan, Patna v2 and Andhra v2 are uniformly lite, and Patna v1, Chhattisgarh v1 and
Karnataka (mostly) are large. Kerala's 17% (9 to 30) agrees with the random-length Kerala sample (11.6%), which
is the only check made that this sample's restriction to short chunks (342 to 3,000 characters, median 768)
does not bias the shares. It is one court, and the model follows the ingestion batch, not length, so no bias is
expected; none was tested elsewhere.

**The dead-vector detector could not have caught any of this.** It scores a stored vector's cosine with the
mean legal-text direction. Measured on these 2,640 vectors, by identified model: `voyage-4` mean 0.60
(minimum 0.29), `voyage-4-lite` mean 0.63 (0.20), `voyage-4-large` mean 0.56 (0.26); **none of the 1,931
off-`voyage-4` vectors fell below the 0.10 threshold**, and only the 2 dead vectors did. A lite or large
vector of legal text looks like a healthy one to the detector, which is why the 9 off-model Kerala chunks
sat in the healthy set. (The figure of about 0.45 quoted for a healthy vector is the Kerala live population
of section 17; across courts the means are higher.) So the 200,339-chunk, 73-court scan, and the 275,216
non-Kerala chunks of section 16, **carry no information about model mixing**. "Clean" in sections 14 and 16
means "no dead vectors", never "one model". If anything the detector is slightly miscalibrated across models:
the 4 cross-court false positives of section 16 were live chunks from another model scoring 0.093 to 0.097.

**Added 3 Nov 2026: the detector's "healthy" range depends on chunk length, and 0.56 to 0.63 does not hold for
long chunks.** The range above comes from the 2,640-chunk sample, which used short chunks (342 to 3,000
characters, median 768). Measured on the Supreme Court: Vaquill's own stored `voyage-4-large` vectors in
`kanoon_v1` (4,000 sampled, mostly 3,000+ characters) score **median 0.270, with 44 of 4,000 (1.1%) below the
0.10 line**, and the score falls with length (r = -0.26). The 10,112 newly embedded Supreme Court chunks (median
3,914 characters) score median 0.304, 1 of 10,112 (0.01%) below 0.10, and that one re-embeds to its stored vector
at cosine 1.000000, so it is a false positive of the same kind. **Read the detector as length-dependent:** below
0.10 is a strong signal for a short chunk, and for a long one (3,000 characters or more) roughly 1% of healthy
vectors fall under it. The Kerala count (217,766 flagged, confirmed by re-embedding from both sides of the cut in
section 16) is not affected, because it was confirmed by re-embedding, not by the threshold alone; a future use of
the threshold on long chunks should confirm a flag the same way.

**Direction of the error: false positives on long healthy chunks, not missed dead vectors (stated explicitly,
because "length-dependent" alone can be read the other way).** The length effect pulls healthy long chunks
*toward* the dead range; it does not lift dead vectors out of it. Measured on the 217,766 dead Kerala vectors
(`kerala_flagged.tsv`): median 0.002, 99th percentile 0.066, maximum 0.099 (the flagged set stops at the 0.10
line by construction), and the 159,695 of them with a body of 3,000 characters or more sit at median -0.004,
99th percentile 0.063. A long healthy chunk bottoms out around 0.075 in the new Supreme Court set (minimum 0.075)
and at 0.035 in Vaquill's stored Supreme Court vectors (4,000 sampled, minimum 0.035, 1.1% below 0.10). So dead
and long-healthy overlap only in the band from about 0.035 to 0.10, which is where the roughly 1% of spurious
flags comes from; dead vectors do not score above 0.10 because a chunk is long, so **separation survives and
section 16's clearance of the other courts still holds** (a missed dead vector is not what this effect
produces). **Running the detector over long chunks (3,000 characters or more) would flag about 1% of healthy
ones spuriously** and each flag there needs the re-embedding check. Not measured here: the same effect for
short chunks, where scores run higher for both populations (section 16's length-bucket check, flagged rate 5.0%
below 500 characters against 6.6 to 8.1% above, already covers that).

Nothing here proposes or prices a re-embed; that is the owner's spend decision.

### Qdrant can serve per-court models in one call

On 1.16.3, several dense prefetch branches — each with its own query vector, court filter and
quantization — plus a sparse BM25 branch, fused in one call. Three dense branches plus sparse took
4.1 ms against 2.3 ms for one plus sparse, on the 446k copy. Fuse by **rank (`rrf`), not score**:
the branches' scores come from different models.

### So the cost decision, restated

| Option | Coverage | Cost |
|---|---|---|
| Per-court-majority query models, RRF fusion | ~92% of points matched | **$0**, plus ~1.8 ms of latency |
| Re-embed everything at `voyage-4-lite` | 100% | ~$560 |
| Re-embed everything at `voyage-4` | 100% | ~$1,700 |
| Re-embed everything at `voyage-4-large` | 100% | ~$3,400 |

Measured at ~28B tokens, about 900 tokens a chunk. **The trap:** `kanoon_v1` — what is served
today — is `voyage-4-large` (A120). Matching it means the $3,400 column, not the $1,700 one.
Choosing a cheaper model means re-embedding the launch corpus too, and accepting a weaker model
for the part of the corpus that is currently clean.

**Working answer: the per-court config at $0.** Hybrid is what ships. *(3 Nov 2026: the second sentence of
this answer, "hybrid loses nothing measurable to a mismatched query", was measured on sentence-style queries
against a corpus believed single-model; see the end of this section. The claim that the config itself is load-bearing is WITHDRAWN (4 Nov 2026): the per-court design was dropped, DECISIONS A128.)*

### Two findings in that report that deserve more weight than they got

1. **Dense vectors unrelated to their own text.** 2 of 50 Kerala v2 chunks scored cosine about 0
   under every model. At that rate, ~4% of Kerala's 3.1M chunks are **unfindable by dense search
   at all** — not ranked badly, invisible. It rests on two chunks and is unverified. But section 9
   measured ~48% of `acts_india` carrying raw term counts where BM25 weights belong, so broken
   vectors are an established failure mode in this data, not a fluke. A second class of them in a
   different collection is plausible and cheap to measure. **For the trust promise this is worse
   than any ranking bias:** a chunk that cannot be retrieved cannot be cited, so the user is told
   "not in our dataset" about something the dataset holds.

   **Corrected 3 Nov 2026 (sections 14, 17 and 18).** The claim in the first point is wrong, and
   section 14 only half-corrected it. Not one of the 217,766 dead Kerala points was ever the only
   copy of its chunk: each has a live twin with the same `chunk_id` (section 18). No chunk was
   unfindable by dense search, and the "not in our dataset" failure described here did not occur.

2. **The absolute recall level, which nobody remarked on.** Hybrid recall@50 is 87% — a query
   built from a chunk's own sentences fails to bring that chunk back in the top 50 about one time
   in eight, on a 200k corpus the report itself calls optimistic against 2.8M. Dense-only @10 is
   58%. Known-item is a harsh test (near-identical chunks count as misses, and judgments carry a
   lot of boilerplate), so this understates real performance by some unknown amount. It is still
   the first retrieval-quality number this project has ever had, and 13% of answerable questions
   reaching the gate with nothing above threshold is a product problem, not an embedding problem.

## 14. Measured: the dead vectors are Kerala-only, keyword-findable, and cheap to fix

**Measured**, 3 Nov 2026. 3,144 High Court chunks re-embedded under `voyage-4` and compared with
the stored vector — the 2,642 short chunks from section 13 plus 502 new random-length chunks, with
Kerala v2 over-sampled to 450. Full table: `~/qdrant-kanoon/reports/hc_followup_report.md`.

### The result

- **Kerala v2: 31 of 450 unrelated** (cosine under 0.50) = **6.9%**, 95% CI 4.7–9.6%. The earlier
  4% (2 of 50) was a low draw inside that interval. Not length-specific: 29 of 400 random-length.
- **About 215,000 of Kerala's 3.1M chunks** (range 147,000–300,000), against the ~124,000 the
  earlier estimate implied.
- **Every other court is clean** (**of dead vectors only; this says nothing about which model built them**, section 13): 0 of 2,694 across v1 and v2, 95% upper bound 0.13%. Overall
  0.69% of the 31.0M High Court points, all of it Kerala v2.
- **The text is fine in all 31** — 430 to 4,211 characters, no replacement characters. A bad
  vector, not bad text.
- **The sparse vector is intact in all 31.** Hybrid finds every one of them. **Nothing is
  unreachable by any path**, so the severity is roughly half what section 13 feared: degraded
  ranking, not invisibility, and a citation to such a chunk still verifies.
  **Corrected 3 Nov 2026:** "degraded ranking" is also too strong for the service. Every dead
  point has a live twin with the same `chunk_id` (section 18), so a chunk's dense rank is that of
  its best copy, which was never dead. What the dead copy costs is a wasted slot and a duplicate
  source id, not lost retrieval. The measurements in this section describe the dead copy alone.
- **What they embed is unknown.** Well-formed unit vectors, pairwise cosine 0.33 (not one repeated
  placeholder), cosine **0.00** against the mean legal-text direction where real chunks average
  **0.62**. Title, parties, case number and URL do not reproduce them. Case years 2019 (9 of 31)
  and 2022 (7 of 31) are over-represented.

### Detection is free, and the fix is about $12

The measurement above cost API calls because it re-embedded to compare. **Finding the rest needs
no API calls at all.** The dead vectors score 0.00 against the mean legal-text direction while
real chunks average 0.62 — so one dot product per point separates them, on data already held.

1. Compute the mean legal-text direction once from known-good chunks.
2. Score all 3.1M Kerala vectors against it. Seconds of arithmetic, no vendor.
3. Validate the threshold against the 31 known-dead and 419 known-good before trusting it, and
   report precision and recall of the detector itself.
4. Re-embed only what it flags.

Re-embedding ~215,000 chunks at ~900 tokens is ~194M tokens: about **$12** at `voyage-4` list
price, roughly $23 at `voyage-4-large`. Detecting them by re-embedding all of Kerala instead would
be ~2.8B tokens, about **$167** — so the free detector is worth building before anything is spent.

**But the $12 job is blocked by an unactivated payment method.** At the throttled free tier
(10,000 tokens a minute) 194M tokens is about **13 days**. This is a $12 fix gated by a card, not
by engineering.

### Mixed-corpus ranking bias: real, modest, and it confirms the per-court answer

200,103 Delhi v1 points (≈28% `voyage-4` / 72% `voyage-4-large`), 240 queries over 115 labelled
chunks, each run under a matched and a mismatched query model.

| | Dense | Hybrid |
|---|---|---|
| Matched ranks it better / worse (of 240) | 82 / 16 | 48 / 13 |
| Mean rank, matched vs mismatched | 11.7 vs 14.8 | 5.2 vs 5.9 |
| recall@10, `voyage-4`-built chunks | 82% vs 74% | 94% vs 93% |
| recall@10, `voyage-4-large`-built chunks | 70% vs 62% | 89% vs 87% |

The bias is real and BM25 absorbs most of it. **The best single query model is the court's majority
model**, which is exactly the per-court-majority config section 13 proposed. That decision is now
measured from both directions and can be treated as settled: **$0, not $1,900.**

### Recall falls with corpus size, which makes the court filter a recall mechanism

Hybrid recall@50 measured at 91%, 91%, 89%, 87% on 25k, 50k, 100k and 200k points. Extrapolated
(roughly, from 20 target chunks): **about 82% at 2.8M and about 77% at 31M** if a user searches all
High Court data with no court filter.

**Architecture consequence nobody had stated:** the filter step is not only about relevance. An
unfiltered 31M search loses about ten points of recall against a single-court search. Filters
should be treated as part of how the product finds things, not as a refinement.

The 87% figure itself pulls both ways and the net sign is unmeasured: it **understates** because
only the exact source chunk counts, and 3 of 7 hybrid misses had another top-50 chunk carrying the
same sentence verbatim (counting those lifts it to 93%); it **overstates** because the queries are
the chunk's own sentences, handing BM25 an exact lexical match that a real paraphrase would not.
Stripping names and numbers took strict recall 91% to 81%. **What would settle it is the thing the
200-question set is waiting for:** real questions with labelled answer chunks, not sentences lifted
from the chunks themselves.


## 15. The dead-vector detector is validated, and `court` can be flatly WRONG

**Measured**, 3 Nov 2026, across the four pre-spend checks.

### The detector works, and better than proposed

Each stored vector is scored by its cosine with the mean legal-text direction, built from 2,694
good chunks of **other** courts so the Kerala test has no leakage.

| | Score range |
|---|---|
| 31 dead Kerala chunks | −0.063 to +0.046 (mean −0.006) |
| 419 good Kerala chunks | +0.159 to +0.689 |

**AUC 1.000.** At a threshold of **0.10** — the middle of the gap — it caught 31 of 31 and flagged
0 of 3,113 good chunks. Precision and recall both 100%.

Two limits worth keeping: good chunks score lower the longer they are (mean 0.45 at 3,000–5,000
characters), so the threshold must not drift much above 0.15; and recall is evidenced only on
Kerala's 31, because no other court had any dead vectors to test against.

Applying it costs no API calls but needs the stored vectors of all 3.1M Kerala chunks — about
3–4 hours of read-only reads at ~240 points a second. **That read can start before the payment
method is live**, because it spends nothing.

### Re-embedding genuinely repairs them

100,038 Kerala points in a scratch instance, 20 known-dead chunks and 20 healthy controls, dense
vector replaced only.

| | Dense recall@10 / @50 | Hybrid recall@10 / @50 |
|---|---|---|
| Dead, before | **0% / 0%** | 61% / 89% |
| Dead, after | 41% / 50% | 73% / 91% |
| Healthy controls | 37% / 47% | 73% / 86% |

Rank improved on 22 queries and worsened on none; detector score went −0.01 to +0.47. **After the
fix the dead chunks perform at the level of healthy ones**, which is the right success criterion.
Hybrid barely moves, confirming section 14: the intact sparse vectors were already carrying them.
Cost of the proof: ~33,000 tokens.

### Scope: the job does not double — but the data told a lie on the way

Kerala is **not** in `legal_corpus_v1`. About 760 Kerala chunks hide in v2's 75,786 no-court
points (3 of 300 sampled), which the detector would also reach. Kerala v2's majority model is
`voyage-4` (368 of 450), so dead chunks are re-embedded with that.

**The finding that outlives this task:** the 17 points v1 labels `High Court of Kerala` are all
**Uttarakhand** chunks (`UKHC` prefix). Section 5 recorded that court names are not *canonical* —
spelling variants that make a filter miss records. This is a different and worse failure: a court
label that is simply **wrong**, so a filter on one court silently returns another court's
judgments. Consequences nobody has accounted for:

- A user filtering to a court can be shown a different court's law.
- The per-court embedding-model config (section 13) keys on `court`, so a mislabelled record gets
  queried with the wrong model.
- Section 14 showed the court filter is also a **recall** mechanism at scale, so a wrong label
  costs recall as well as correctness.

Seen in 17 points, which is tiny — but nobody has measured how often `court` is wrong rather than
merely spelled differently, and the three consequences above all assume it is right.

## 16. The full Kerala scan: 217,766 dead, the threshold holds, no other court affected

**Measured**, 3 Nov 2026, full scan with the fixed scorer. Source: `~/qdrant-kanoon/reports/
kerala_scan_report.md`, `scan_confirm.log`, `scan/kerala_v2.tsv`.

### The count

**217,766 flagged** — 217,688 of Kerala v2's 3,125,018 chunks (**6.97%**), plus 78 of the 909
`KLHC` chunks hiding in v2's no-court group. Against section 14's 215,000 estimate, which came
from a 450-chunk sample: close enough to be reassuring, but the checks below are the evidence,
not the closeness.

### The gap survived at scale — this is the finding that validates the threshold

The worry was that a clean separation on 450 chunks would dissolve into a continuum at 3.1M,
making the 0.10 cut arbitrary. It did not.

- Dead cluster: **−0.12 to +0.099**, mean +0.003, sd 0.030.
- The valley between 0.09 and 0.13 holds **31, 5, 14, 16 and 65** chunks per 0.01 bin.
- The two peaks hold **102,250 and 680,629** chunks per 0.05 bin.

The valley is about four orders of magnitude below the peaks. And the cut is insensitive:
**moving it from 0.08 to 0.14 changes the flagged count by −243 to +100** — under 0.2% across a
range six times wider than the threshold's own uncertainty. The number does not depend on where
in the valley the line is drawn.

### Length contamination: ruled out

Section 14 flagged that good chunks score lower the longer they are, so long legitimate chunks
might be swept in. They were not. Flagged median body length **3,784** characters against
**3,840** for all Kerala chunks, and the flagged rate is **6.6–8.1% in every length bucket of 500
characters or more**. Below 500 characters it is 5.0% (n=5,500). No skew.

### Confirmed by re-embedding, from both sides of the cut

59 chunks, 66,483 Voyage tokens.

| Group | Result |
|---|---|
| 30 random flagged | **30 dead** |
| 10 flagged near the cut (0.05–0.10) | **10 dead** |
| 5 flagged Kerala no-court | **5 dead** |
| 10 just **above** the cut (0.135–0.148) | **10 live** (cosine 0.95–1.00) |
| 4 flagged in other courts | **4 live** (cosine 0.94–0.95) |

**45 of 45** flagged Kerala chunks confirmed dead, and **10 of 10** just above the cut confirmed
live. Validating both sides of the boundary is what makes 217,766 a count rather than an estimate.

### Every other court is clean — now with a real denominator

**"Clean" here means no dead vectors. The detector cannot see which model built a vector** (section 13: a
`voyage-4-lite` or `voyage-4-large` vector scores like a healthy one), so this scan carries no information
about model mixing and must not be read as if it did.

The 4 cross-court flags are **false positives**: live chunks whose embedding model differs from
the detector's reference direction, scoring 0.093–0.097. So **0 confirmed dead outside Kerala**,
out of **275,216** non-Kerala chunks scored (200,339 across 73 court files plus 74,877 non-Kerala
no-court points). Pooled bound about 0.001%.

Section 14's "0 of 2,694" rested on ~35 chunks a court. This is two orders of magnitude better,
and it confirms the job is Kerala's alone.

### Two things the reconciliation turned up

**A reporting error the session found and fixed itself.** The report's line 2 said 200,023 and
line 7 said 275,216. The first was a *planned quota* read out of `driver.log`, never a result;
the actual written count was 200,339, and the real denominator adds the 74,877 non-Kerala
no-court points. The session reconciled both figures against the scan files, corrected the
report, and also corrected its own earlier claim about the J&K denominator (4,800 → 5,907).

**A duplicated `chunk_id`, and it may matter to the verifier.** The two J&K flags are **one**
chunk id (`JKHC020055362012_005`) stored on **two points**, with identical score, length and
chunk index — "the same duplicated-chunk-id pattern as in the Supreme Court data". So three
distinct chunks were flagged, not four.

*Verified at `adapters/qdrant.py:375-380`:* `get_record` filters on `{"chunk_id": record_id}` and
returns **one** `RecordText`. Verifier check 3 matches quoted words against *that* record's text.
If two points share a `chunk_id` **and their text differs**, the verifier can compare a quote
against a different point's text than the one retrieved, and strip a legitimate citation
nondeterministically. That fails closed, so it is safe rather than dangerous — but it would
remove real authorities for no reason, and the user would be told one could not be verified.

**Unmeasured, and cheap:** how many `chunk_id` values appear on more than one point, and whether
duplicates ever carry *different* text. If duplicates are always identical copies, this is
harmless. Nobody has checked. It connects to `CLAUDE.md` §6's existing warning that `case_id` is
not one per case.


## 17. The Kerala fix lives in `kerala_v2_fix`, not in the original

**3 Nov 2026.** The re-embed wrote to a staging collection, **`kerala_v2_fix`** on the copy
instance. `legal_corpus_v2` was deliberately **not** touched, so the original still holds the
217,766 dead vectors.

**This is a trap waiting for whoever builds Kerala.** Nothing serves Kerala today — it is a
post-gate court (`CLAUDE.md` §1). So `kerala_v2_fix` is now the only good copy of Kerala's dense
vectors, and the obvious move when building a Kerala serving collection is to read
`legal_corpus_v2`, which would silently discard every repaired vector and reinstate a 6.97%
dead rate.

**Rule: any collection that will serve Kerala is built from `kerala_v2_fix`, never from
`legal_corpus_v2`.** If the staging collection is ever lost, the repair must be re-run before
Kerala is served — the detector makes finding the dead vectors free, so this is recoverable, but
only if someone notices.

### Token count per chunk was 39% higher than assumed

The $11.8 figure in `COSTS.md` rested on **900 tokens a chunk**, which was an estimate that got
carried forward as though measured. Measured on 300 random flagged chunks: **about 1,250**. So
the job is ~269M tokens and about **$16**, not ~196M and $11.8.

Two consequences beyond this job:

- The 250M cap set for the run was below the real requirement and would have stopped it at ~93%,
  leaving roughly 15,000 chunks dead. Raised to 300M.
- **Section 13's full-corpus re-embedding prices are built on the same 900-token assumption** and
  are therefore low by the same proportion: ~28B tokens becomes ~39B, so `voyage-4` is nearer
  **$2,300** than $1,700, and `voyage-4-large` nearer **$4,700** than $3,400. Those are not being
  spent — the per-court config settled that at $0 — but the figures should not be quoted as they
  stand. **Unverified:** whether 1,250 tokens a chunk holds outside Kerala; it is measured only
  on Kerala flagged chunks.

### What the run confirmed on the way

- **The rate limit is real:** `voyage-4` sustained 5.0M tokens a minute, `voyage-4-large` 6.3M in
  a burst, neither hitting a ceiling, against the old 10,000 TPM / 3 RPM.
- **Pre-flight passed:** 5 known-live Kerala chunks reproduced at cosine 0.99998–0.99999, so the
  model and pipeline were right before anything was written.
- **A 300-chunk trial was checked before the full run:** all 300 scored at most 0.08 against
  their old vectors (so the dense vector genuinely changed), and all 300 had **byte-identical
  payload and sparse vectors**. That is the check that proves the write touched only what it
  should.

### The run finished: counts, spend and the four verifications

**3 Nov 2026.** All 217,766 dead Kerala vectors are re-embedded into `kerala_v2_fix` with
`voyage-4` (read from `VOYAGE_EMBED_MODELS["kerala_v2_fix"]`; overrides refused). Decision A123.

| | |
|---|---|
| Written | 217,766 of 217,766, none skipped; the collection holds exactly 217,766 points |
| Cap stop | the first process stopped at the old 250M cap after 199,400 chunks (91.6%) and was resumed from its checkpoint (`done_batches.log`, one fsynced line per batch of 100) under the 300M cap |
| Tokens | **272.66M** for the whole task (probes, estimate, pre-flight, run, verification); about **$16.36** at the $0.06 per million list price |
| Time | 36.1 min, then 6.2 min after the resume; about 4.7M tokens a minute |
| Original reads | 2,180 read-only retrieves, slowest 0.54 s, none failed |
| Old vs new vector | cosine max 0.133, mean -0.002: none of the 217,766 old vectors is a `voyage-4` embedding of its own text (but they are not noise; see the misalignment subsection) |
| Backup | old dense vectors in `~/qdrant-kanoon/kerala_fix/old_dense.f32` (217,766 x 1024), no all-zero row |
| Byte-identical | 2,000-point spot-check: 0 payload mismatches, 0 sparse mismatches, 0 points still holding the old dense vector |

Verification, all four requested checks:

1. **Detector re-score** (3,000 rewritten chunks): mean **+0.440**, min +0.161, none below 0.10.
   The old vectors of the same chunks scored +0.003 (100% below 0.10); the live Kerala population
   is +0.455.
2. **Re-embed 20 under `voyage-4`** against what was written: minimum 0.99998.
3. **The same 20 under `voyage-4-large`** (negative control): 0.931 to 0.959, mean 0.947. They do
   not match, as expected.
4. **Dense recall** (scratch corpus of 100,330 points, sentence queries):

| | recall@10 | recall@50 | mean rank | queries |
|---|---|---|---|---|
| Dead, before | 0% | 0% | 51.0 | 505 |
| Dead, after | **34%** | **46%** | 31.4 | 505 |
| Healthy controls | 43% | 54% | 27.3 | 344 |
| Hybrid, dead, before / after | 73% / 76% | 88% / 89% | 12.2 / 10.9 | 505 |
| Hybrid, healthy | 78% | 88% | 9.4 | 344 |

**The success criterion was "reach the level of healthy chunks". On dense recall this run did not
clearly reach it:** 34% against 43% at 10 and 46% against 54% at 50, from a start of zero. Hybrid
is within 2 points at 10 and level at 50. The earlier 20-target scratch proof had them at 41%
against 37%. The vectors themselves are right (check 2 reproduces them exactly), so this is
not a bad write. Whether the gap is real is answered in the next subsection: it is.

**Not done, needs explicit approval:** promoting the fixed vectors into `legal_corpus_v2` (a write
to an original), and the 10,112 Supreme Court chunks (`voyage-4-large` into `kanoon_v1`). The
scratch collection `kerala_recall_eval` is still on the copy instance.

### Check 4 again with matched controls: the dense gap survives

**3 Nov 2026.** Section 14 suggested the dead set over-represents case years 2019 and 2022, so
repaired chunks versus random healthy ones might compare two different content populations. Re-run
locally (no Voyage calls; the 146 existing controls re-weighted to the targets' mix, 2,000-draw
bootstrap over chunks), `~/qdrant-kanoon/kerala_fix/recall_before_after.json` plus
`kfix_matched.py`. Gap = repaired targets minus healthy controls, after the fix.

| Controls matched on | Dense @10 | Dense @50 | Hybrid @10 | Hybrid @50 |
|---|---|---|---|---|
| Nothing (as reported) | -9.4 | -8.2 | -2.6 | +0.1 |
| Filing year (case id) | -13.6 [-22.8, -3.0] | -11.8 | -6.2 | -2.1 |
| Decision year (payload) | -12.8 [-22.5, -3.5] | -12.5 | -8.1 | -2.9 |
| Case length (chunks per case) | -10.9 [-19.3, -2.6] | -9.8 | -6.3 | -2.0 |
| Case length x 2019-or-not | -10.6 [-19.3, -1.6] | -10.1 | -5.7 | -1.4 |
| Chunk length (characters) | -8.1 [-16.9, +0.6] | -7.1 | -2.2 | +0.2 |

Points of recall; brackets are 95% intervals for the @10 gap. **Matching on year does not close the
gap, it widens it; no matching closes it.** Only chunk length brings the interval up to zero, and
the point estimate is still -8. Hybrid is within noise at @50 under every match and short of
healthy by 2 to 8 points at @10.

What the data says about the premise:

- **The year skew is real but is mostly 2019 and mild elsewhere.** Over the full 217,766 dead
  chunks, filing year 2019 is 20.8% of them against 11.9% of the 100k Kerala slice. 2022 is 10.7%
  against 9.3%. 2018 and 2023 are under-represented (3.5% against 7.5%, 5.3% against 11.0%).
- **"Healthy chunks from the same cases" cannot exist.** Dead chunks come in whole cases: of the
  91,275 cases with a dead chunk, 99.9% are dead in every chunk, and only 18 have two or more
  healthy chunks. The defect follows the document, not the chunk, which also fits section 12's
  by-document model mixing. Year was the available fallback.
- **The repaired targets sit in shorter cases:** 90 of 198 are in cases of 1 or 2 chunks, against
  50 of 146 controls. Matching on that does not close the gap.
- **A bias that favours the targets, untested in size:** in the eval corpus, the sibling chunks of
  a repaired target still carry their dead vectors, so they cannot compete in dense search, while a
  healthy control's siblings are live and do. About half of each group has any sibling in the
  corpus (52% targets, 46% controls), so the effect is partial. If anything, a corpus where every
  dead vector is repaired should do **worse** than 34% for these chunks, not better.

**Conclusion: the repaired chunks do not reach healthy dense recall, and neither year nor case
length nor chunk length explains why.** The cause is unknown. What is known: the vectors are exactly
what `voyage-4` produces for the stored text (check 2), the sparse and payload are untouched, and
hybrid search, which is what the product uses, is within a few points of healthy. One candidate cause
is now refuted (next subsection): near-duplicate crowding. Still untested: the text of a dead case
differing from the text that was embedded when the collection was built. A fresh matched draw (healthy chunks chosen
by case length and year, about 500 new query embeddings, a fraction of a cent) would tighten the
intervals, and could move the point estimates; nothing here predicts which way. **Do not promote into `legal_corpus_v2` or
serve Kerala on the strength of "at parity"; it is not.**

### Is known-item recall depressed by near-duplicates? No: the gap lives in the queries that have none

**3 Nov 2026.** Known-item retrieval counts a near-identical chunk as a miss. If dead cases hold more
near-identical chunks than healthy ones, the metric would penalise them whatever the vector quality.
Measured on the text of the whole 100,326-chunk eval corpus (read-only from the original, sentence
hashes kept, `kfix_pool.py` and `kfix_dups.py`), no Voyage calls.

**At chunk level, dead chunks are somewhat denser in repeated text.** Share of a chunk's sentences
(70 to 260 characters) that appear verbatim in another chunk: dead 41.3% against healthy 35.9%;
chunks with any shared sentence 69.0% against 56.6%. Ignoring digits, case and punctuation: 44.3%
against 37.8%. A real difference, but not large.

**At query level it does not appear, and the prediction fails.** The queries are sentences taken
from the chunk, so what matters is how many other chunks contain that sentence:

| | Repaired targets | Healthy controls |
|---|---|---|
| Queries with at least one duplicate elsewhere | 33.5% | 36.9% |
| Queries with five or more | 20.4% | 20.6% |
| Mean duplicates per query | 10.8 | 8.8 |

The two groups face the same duplicate burden. If duplicates caused the gap it would sit in the
queries that have them and vanish in the ones that do not. It is the reverse:

| Gap, targets minus controls | Dense @10 | Dense @50 | Hybrid @10 | Hybrid @50 |
|---|---|---|---|---|
| Queries with NO duplicate (132 targets, 87 controls) | **-15.9** [-26.1, -5.5] | -12.9 [-22.2, -2.9] | -5.9 [-11.0, -1.0] | **-5.0** [-8.5, -1.6] |
| Queries WITH a duplicate (85, 68) | 0.0 [-12.0, +12.0] | n/a | n/a | +7.6 [-3.5, +18.9] |

Where a duplicate exists the two groups are level. Where known-item cannot be penalised by one, the
repaired chunks are clearly behind. **So the gap is not a measurement artefact.**

**Correction to the earlier reading of hybrid.** Section 17 said hybrid @50 was within noise under
every match. That holds for the overall number (89% against 88%) because the targets do better where
duplicates exist and worse where they do not, and the two cancel. In the no-duplicate subset hybrid
@50 is 5.0 points short, interval excluding zero. Hybrid is much closer to healthy than dense is, but
it is not shown to be at parity.

### Sibling bias: free proxy done, the real rebuild test is pending

`kerala_recall_eval2` (100,326 points) is built on the copy instance with **every** dead vector in
it replaced by its repaired one (6,906 in the slice), so no repaired target has a dead sibling.
Running it needed the 849 check-4 query texts re-embedded with `voyage-4` (the first run did not save
the query vectors): 45,856 tokens, under a cent. **Run afterwards, owner-approved; results in the
next subsection.**

A free proxy from the saved ranks, splitting by whether the chunk's case has other chunks in the
corpus:

| Dense recall @10 / @50 | No sibling in corpus | Has sibling(s) |
|---|---|---|
| Healthy controls | 50% / 60% | 30% / 43% |
| Repaired targets (siblings still dead) | 37% / 50% | 27% / 39% |

Two readings. **(1) Siblings do cost recall:** a healthy chunk whose case-mates are live loses about
20 points at @10. **(2) The gap does not need siblings:** among chunks with none in the corpus, so
the sibling bias cannot be acting, the targets are still 13 points behind at @10 (37% against 50%)
and 10 behind at @50. So the sibling bias is not what explains the gap, though it may make a fully
repaired corpus score lower still; the rebuild run is the test of that.

### Sibling bias, tested: a fully repaired corpus scores a little lower, as predicted

**3 Nov 2026.** The same 849 queries, re-embedded (`voyage-4`, query side, 45,856 tokens), run against
two collections on the copy instance: **A** the original check-4 corpus (some siblings still dead) and
**B** `kerala_recall_eval2`, where every dead vector in the 100k slice is repaired. Control: A
reproduced the earlier numbers (dense 34% / 46%, healthy 43% / 54%), so the new query vectors behave
like the old ones. Query vectors are now saved in `kerala_fix/query_vectors.npy`.

| Repaired targets | A | B | Change (paired, 95% interval) |
|---|---|---|---|
| Dense recall @10 | 34% | 32% | -1.2 [-2.2, -0.4]; 6 hit-to-miss, 0 miss-to-hit |
| Dense recall @50 | 46% | 45% | -1.6 [-3.0, -0.6]; 8 hit-to-miss, 0 miss-to-hit |
| Hybrid recall @50 | 89% | 89% | +0.2 |

Healthy controls moved +0.6 (@10) and +2.6 (@50, interval 0.0 to +5.4), which is noise-sized.

| Gap, targets minus controls | A | B |
|---|---|---|
| Dense @10 | -9.4 [-18.1, -0.6] | -11.1 [-19.2, -2.0] |
| Dense @50 | -8.2 [-16.4, +0.1] | -12.4 [-21.2, -4.0] |
| Hybrid @10 | -3.0 | -4.4 |
| Hybrid @50 | +0.1 | +0.3 |

**The prediction holds in direction and is small in size:** repairing the siblings costs these
chunks a point or two, so the sibling bias explains little of a 9 to 12 point gap. Dense @50 in A
was at the edge of significance and in B it clears it.

### Script composition tested: Malayalam does not explain the gap

**3 Nov 2026.** Counted on the text of all 100,326 chunks of the eval corpus (read-only from the
original, counts only kept; `kfix_script_pool.py`, `kfix_scripts.py`).

| | Dead chunks (7,104) | Healthy chunks (93,222) |
|---|---|---|
| Any Malayalam character | 0.3% | 0.2% |
| Mean Malayalam share of characters | 0.018% | 0.027% |
| Any non-Latin letter | 0.4% | 0.3% |
| Any non-ASCII character | 22.4% | 30.0% |
| ...of which typographic only (quotes, dashes) | 22.0% | 29.7% |

Case level (4,624 dead cases, 67,714 healthy, judged by their chunks in the corpus): any Malayalam
0.4% against 0.3%. **Malayalam is nearly absent from this corpus** (0.2% to 0.3% of chunks), and the
dead set is not richer in it; if anything it has less non-ASCII text overall. Of the 344 queried
chunks only 3 contain any (2 targets, 1 control), so a mixed-script subset cannot be tested. The 196
targets and 145 controls with **no** Malayalam show the same gap as the whole: dense @10 -11.1
[-19.9, -2.5] in B, -9.6 in A. Hybrid @50 is level there (89% against 89%).

**Script is not the cause.** Caveats: the corpus is the first 100,000 Kerala v2 points, about 3.2% of
the court, and annexures in Malayalam may sit in parts of the court it does not reach or may not be in
the extracted text at all.

### What is left

Ruled out as the cause of the residual dense gap, each measured: case year, case length, chunk length,
near-duplicate crowding, sibling state, script. **Left: the stored text of a dead case differs from the
text that was embedded when the collection was built.** That needs its own design. The repair itself
is not in question for a `voyage-4` collection: the old vectors do not match their own stored text under
`voyage-4`. But see the next two subsections: they are not corruption, which changes what the mechanism is.

### Is an old vector the embedding of some OTHER chunk's text? No, and it is not noise either

**3 Nov 2026.** Local only: the backed-up old vectors against the repaired ones (which are the true
`voyage-4` embeddings of the stored text), plus 23,269 healthy stored vectors from the slice
(`kfix_misalign.py`, `kfix_neighbours.py`).

| | Result |
|---|---|
| Best match of an old vector among all 217,766 repaired vectors (itself excluded) | median 0.110, max 0.190; **none at or above 0.5** |
| Best match among 23,269 healthy Kerala vectors | median 0.101, max 0.176; none at or above 0.9 |
| For comparison: a repaired vector's best match among the others | median 0.896 |
| Old vector against its own repaired vector | -0.002 |

**So there is no shuffle of vectors against text:** no old vector is a `voyage-4` embedding of any
chunk in the dead set or the healthy sample. This also follows from the detector itself: a valid
embedding of legal text scores about +0.45, the old vectors score +0.003.

**But the old vectors are not garbage.** They keep the geometry of text similarity:

- The top 10 neighbours of a chunk inside the dead set are the same chunks under the old vectors and
  the repaired ones **50.0% of the time** (3,000 chunks; chance is 0.005%); 57.5% of chunks share five or
  more. Counting only neighbours from other cases: 48.2%.
- Pairwise cosines are preserved: two chunks of the same case 0.705 (old) against 0.736 (repaired);
  random pairs 0.349 against 0.353; near-duplicate chunks have near-identical old vectors (best
  match 1.000 at the 99th percentile in both spaces).
- A linear map fitted between the two spaces, with each space's mean vector removed, explains **77% of
  the variance** on held-out chunks (cosine 0.88, shuffled baseline 0.000). It is not a single
  rotation: an orthogonal fit reaches only 0.86 (0.999 would be a rotation), and there is no dimension
  permutation (best per-dimension correlation 0.77).

**Reading:** the old vectors are real embeddings of the same text, in a space that is **not** the
`voyage-4` family's shared one. The most likely explanation is a **different embedding model** run on
those documents (the dead set is whole cases, 99.9% of them), the same by-document batch mixing as
section 12, except that this batch left the shared space entirely. **Not verified:** which model. None
of the other Voyage families was ever tested against these vectors (a probe of about 20 chunks across
six models would cost on the order of a cent).

What this changes:

- **The vectors were not corrupted, and they were not "wrong" in themselves.** They are wrong for a
  collection queried with `voyage-4`. Our earlier wording ("unrelated to their text") overstated it.
  The re-embed is still correct for a `voyage-4` collection and was verified; it is just a model
  replacement, not a data repair.
- **Recurrence.** The mechanism (a batch of cases embedded outside the family) can occur in any court.
  The detector would catch it, because such vectors score near zero against the legal direction, and
  it found none in 200,339 sampled chunks of 73 other-court files (4 live false positives); the
  per-court upper bound is about 0.06% at roughly 4,800 chunks each, so a small batch could still be
  missed. **A true shuffle (a vector belonging to another chunk) would NOT be caught by the
  detector**, since a shuffled vector still looks like legal text. None was found here, and the only
  check elsewhere is the per-court reproduction sample of about 35 chunks (section 13).

### Semantic crowding: not the cause

**3 Nov 2026.** The duplicate test above was verbatim. This one is semantic: for each target and
control, the cosine to its nearest neighbours in the fully repaired corpus (`kerala_recall_eval2`,
exact search, neighbours from other cases only; `kfix_crowd.py`).

| | Repaired targets (198) | Healthy controls (146) | p |
|---|---|---|---|
| Cosine to the nearest other-case chunk | 0.846 | 0.840 | 0.63 |
| Mean of the 5 nearest | 0.823 | 0.814 | 0.52 |
| Other-case chunks at cosine 0.90 or more | 11.9 | 15.0 | 0.20 |
| Other-case chunks at cosine 0.95 or more | 4.4 | 6.9 | 0.095 |

**The targets are not in denser neighbourhoods; if anything they have fewer very close neighbours.**
Matched on neighbourhood density (tertiles), the dense @10 gap is -6, -24 and +0.5 points in the
sparse, middle and dense tertiles: not monotone, and 40 to 75 chunks per cell. The gap does not follow
density.

One query-level difference does appear: a query is **less similar to its own repaired chunk**, 0.489
against 0.511 (difference -0.021, 95% interval -0.039 to -0.003), while the best competitor is equally
strong (0.567 against 0.560). Split by chunk length the differences are -0.007, -0.021 and -0.011, none
significant alone. This does not account for the recall gap: at the same own-similarity the targets
still trail where it is high (own cosine 0.60 or more: 54% against 76% found in the top 10, 80 queries
each). **Crowding is ruled out; the cause of the dense gap remains unknown.**

### Limitation: one slice

Every recall measurement in this section (check 4, the matched controls, the duplicate, sibling, script
and crowding tests) used the same first 100,000 Kerala v2 points (3.2% of the court), plus the
rewritten targets and controls drawn from the whole of Kerala and the other courts. The dead rate in
that slice (6.89%) matches the court's (6.97%), but one matching dimension does not make a slice
representative: the slice could differ in year mix, case type, case length or court bench in ways
that were not checked, and none of the results here should be read as estimates for the whole court.

### The twin hypothesis, tested: duplicates do not explain the recall gap

**Hypothesis (from the duplicate finding):** the dense gap lives almost entirely in targets whose chunk
has a twin point in the corpus. **3 Nov 2026, free and local:** the saved query vectors against
`kerala_recall_eval2` on the copy instance, no Voyage calls, nothing written to any Qdrant.

**The match key was the point id, not the chunk id.** Check 4 scored a query a hit when the target's
point id was in the top k (`q["id"] in ids`, `kfix_rerun.py`). A twin of the target is a different
point id with the same text, so it could take the target's place and count as a miss. I therefore
re-scored every query under both keys (`kfix_twin.py`, results in `recall_twin.json`).

**Result: the hypothesis fails.** In the searched corpus only **21 of 849 queries** have a target whose
chunk_id sits on two points (18 repaired-dead targets, 7 distinct chunks; 3 healthy, 1 chunk). The other
**828 queries have no twin in the corpus and carry the whole gap**:

| Healthy minus repaired (percentage points, 95% cluster-bootstrap CI over targets) | dense @10 | dense @50 |
|---|---|---|
| All 849 queries, point-id key (as originally run) | 11.1 (2.6 to 19.7) | 12.4 (3.7 to 20.7) |
| All 849 queries, chunk-id key | 11.1 (2.7 to 19.9) | 12.4 (4.0 to 21.1) |
| The 828 queries with no twin | **10.0** (1.3 to 18.9) | **12.2** (3.8 to 20.8) |

Scoring by chunk id instead of point id changes dense recall for no group and hybrid @10 for the
duplicated targets alone (61% to 67%, 18 queries). Removing the duplicated queries leaves the gap at 10.0
and 12.2 points. The gap sits where there are no twins, so twins do not produce it. These are raw,
unmatched gaps in this corpus; the matched figures are in the subsection above.

**The crowding test could not have seen a twin**, as pointed out: it measured the nearest neighbour
from another case, which excludes a same-chunk twin by construction. This test is the one that looks
for it.

**What the eval cannot say.** Only 3.2% of Kerala is in the 100,000-point slice, so a target's twin is
in the slice about 3% of the time. That is why 7 of 198 targets have one. The eval therefore measures
a repaired vector with no twin competing. In the real service every dead chunk has a twin
(section 18), which makes this gap irrelevant to what a user would see: the live copy answers, at the
healthy rate. The gap remains unexplained as a property of the repaired vectors, and the claim that
it is a measurement artefact is **not** supported, because the cause was not duplicates.

### Is it the embedding call? No: the adapter test (and the gap's tenth hypothesis)

**3 Nov 2026.** The question: does our call to Voyage sit off the corpus's own space, so that a chunk
we embed (the pending 10,112 Supreme Court chunks, which have no twin) would carry the dense penalty?

**What is actually sent** (read from the code, not from intent):

| Setting | `adapters/voyage.py` `VoyageClient.embed` | `data/dead_vectors/reembed_kerala.py` `voyage_embed` (the Kerala fix) |
|---|---|---|
| Purpose | **queries only** | documents |
| `input_type` | `"query"` | `"document"` |
| model | `settings.embed_model_for(collection)` | `settings.embed_model_for("kerala_v2_fix")` = `voyage-4`; overrides refused |
| `output_dimension` | **not sent** (API default, 1024) | `1024` |
| `output_dtype`, `truncation`, `encoding_format` | **not sent** (API defaults: float, truncation on) | **not sent** (same defaults) |
| Text preprocessing | none: the text goes in verbatim, one per request | none: the stored payload `text` goes in verbatim, 50 per request; no strip, no normalisation, no header removal or title prepending |

**The adapter has no document-embedding path at all.** The Kerala fix, and any future SC embed, use a
separate script that sends `document`. The adapter's `query` setting is correct for queries and
**wrong for documents**: measured 2 Nov on SC chunks, `input_type=query` against the stored vectors gives
cosine **0.82 to 0.90**, which is exactly the offset the question feared. A chunk embedded through
`VoyageClient.embed` would ship that offset. The `embed_new_sc.py` plan sends `document` (and its `--go`
is not implemented), so it is not exposed, but the trap is real: the next person to need a document
vector will find `embed` and use it. Nothing was changed; adding a document method is a decision to record
first.

**Result, 50 healthy Kerala chunks** (random, drawn without looking at any cosine, through the Kerala fix's
own `voyage_embed`, `voyage-4`, 64,727 tokens, about Rs 0.33), cosine against the vector stored in the corpus:

| Cosine to the stored vector | Chunks |
|---|---:|
| 0.998 or more | **41** (median 0.99999) |
| 0.99 to 0.998 | 0 |
| 0.90 to 0.99 | 9 (0.937 to 0.959) |
| below 0.90 | 0 |

Mean 0.991, which hides a **bimodal** distribution: 82% reproduce Vaquill's vector exactly and 18% sit at
about 0.95, nothing between. That is not a systematic offset. 0.95 is the agreement between two members of
the `voyage-4` family on the same text (sections 11 to 13: the collections mix `voyage-4`,
`voyage-4-large` and `voyage-4-lite` by document batch), so the 9 are chunks Vaquill embedded with
another model (**inferred from the band, not re-measured here**). The same chunks were low in the earlier,
independent measurement (371 healthy Kerala chunks: 328 at 0.998 or more, 43 at 0.929 to 0.960, none below
0.90; the two runs differ by at most 0.0002 per chunk). Earlier checks agree: 5 of 5 pre-flight chunks at
0.998 or more; SC under `voyage-4-large` and `document`, 20 of 20 at 0.9987 to 0.9995 (the shortfall from
1.0 is storage precision, `part7_why.log`); a v1 High Court chunk under `voyage-4` at 0.999984.
Output dimension, truncation and the default dtype make no difference (same cosines with the setting
omitted); collapsing whitespace costs 0.004, prepending the title 0.003, stripping the header 0.02 to 0.05.

**So the call reproduces the corpus's own vectors, and the hypothesis dies.** It also follows from the
design: for a `voyage-4` chunk the repaired vector is what the same call yields for a healthy chunk, at
cosine 1.0. A defect in the vector cannot explain a recall gap between two sets of vectors made the same
way. The gap, if it is real, comes from which chunks the dead set holds, not from how they were embedded.
Kerala was not "produced with the wrong setting"; `document`, 1024 is the right one.

**The gap, recorded as a known unknown.** Ruled out, each measured: (1) case year and filing year
(matched controls), (2) case length, (3) chunk length, (4) verbatim near-duplicate crowding, (5) sibling
state (corpus fully repaired), (6) script (Malayalam), (7) vector misalignment (old vectors are real
embeddings from another space, not a shuffle), (8) semantic crowding, (9) same-chunk twins, and now
(10) the embedding call. Only 21 of 849 queries have a twin in the eval corpus, which is why (9) failed.
Unexplained: a repaired target still trails a healthy control by about 10 points at dense @10 and 12 at @50;
hybrid is at parity. **Service impact: none for Kerala**, because each dead chunk has a healthy twin and
the service keeps that one (A126). For chunks we would embed that have no twin (SC), this test says the
vector will match what the corpus would have held; it does not prove those chunks will recall at the
healthy rate, because the gap is a property of the population and was not explained.
**Limits:** one court, one model (`voyage-4`) in this run; the SC path (`voyage-4-large`) rests on the
2 Nov pre-flight and was not re-run; 50 chunks. (The low group's model was inferred when this was first
written; it is now measured, see section 13: 5 `voyage-4-lite`, 4 `voyage-4-large`.)

**Standing note: the gap is a property of which chunks the dead batch held, not of their vectors.** The
repaired vector is what the same call yields for a healthy chunk, so the vector is not the variable.
Ten hypotheses are measured and ruled out, no user impact has been shown, and Kerala is protected by A126.
**This work stops here.** It is a known unknown and nobody should spend further effort on it as it stands.

**The one condition that reopens it:** the retrieval eval on the Supreme Court chunks that have no twin
(the 10,112 to be embedded). If those show the same penalty (a freshly embedded, twinless chunk trailing a
healthy one by about 10 points at dense @10), the cause is not Kerala-specific and it is reopened. Until that
eval runs, do not chase it.

## 18. Court labels, `act_status` and duplicate chunk ids: measured (interim, the Qdrant scan stopped twice at the 20-second limit)

**3 Nov 2026.** Parquet results are exhaustive (75 files, 33.7M rows). Qdrant results come from
`acts_india` (complete, 1,098,577 points) and the first 200,000 `legal_corpus_v2` points of an
exhaustive read-only scroll (`kfix_idscan.py`, checkpointed). The scan hit the standing 20-second
hard stop on the first `legal_corpus_v2` request and again at page 46; v2 beyond 200,000 and all of v1
are **not yet read**. Nothing was written to any Qdrant.

**Limit raised, 3 Nov 2026.** The owner raised the read-only request limit on the originals from 20 s to 60 s,
citing `CLAUDE.md` section 9. That section's 60 s is for waiting on a service *start*; it says nothing about a
request timeout, so the 60 s rests on the owner's instruction, not on that line. The hard stop and the
no-retry rule are unchanged. The scan has **not** been resumed.

### How often is `court` wrong? Almost never; it is more often missing

| Parquet, 32,572,660 judgment rows | Rows | Share |
|---|---|---|
| Label is the court's usual spelling | 32,315,460 | 99.21% |
| Same court, other spelling (`Patna High Court` / `High Court of Patna`) | 67,598 | 0.21% |
| **No label at all** | **189,320** | **0.58%** |
| **A different court's name** | **282** | **0.00087%** |

**The id is reliable.** 30 prefixes; each maps to exactly one `court_code` and one source file in all
rows; `chunk_id` starts with its `case_id` in all rows. The Supreme Court has no letter prefix.

**A wrong label is a non-problem by rate:** 282 rows in 82 cases (9 Uttarakhand rows labelled Kerala,
71 Delhi rows labelled Patna and the rest). Reading the first chunk's own text for those cases: it names
the id's court in 42, the label's court in 12, both in 9, neither in 19. In Qdrant `legal_corpus_v2`,
first 200,000 points: 7 different-court labels (0.0035%) and 1,303 with no label (0.65%).

**A missing label is the real cost, because a court filter silently drops those rows.** Highest shares
of unlabelled rows: Himachal Pradesh 4.1%, Andhra Pradesh 3.0%, Delhi 2.9%, Orissa 2.1%. Deriving
`court` from the id would fill all of them for free, since the id agrees with `court_code` in every
row. The spelling variants (0.21%) also defeat an exact-string filter unless labels are normalised.

### `act_status`: a default, not a determination. "In force" stays off.

All 22,264 Acts (parquet) and 22,265 (Qdrant `acts_india`: one extra Bihar Act) have `act_status`;
it is constant within every Act. Split by id kind, which is the test:

| Id kind | Acts | `act_status` |
|---|---|---|
| State (`IND_state_`) | 8,544 (Qdrant 8,545) | **in_force 100%** |
| Central (`IND_central_`) | 848 | **in_force 100%** |
| Repealed (`IND_REP_`) | 710 | repealed 100% |
| Regulators and other | 12,162 | in_force 11,774; superseded 378 (all SEBI); spent 10 |

State Acts are uniformly in force and so are central Acts by id. The only variation is where the **id
already says so**: all 710 repealed Acts are exactly the `IND_REP_` ids, so `act_status` adds no repeal
information the id does not carry. That is the signature of a default. **"In force" stays off
permanently** (`SHOW_IN_FORCE`); it currently withholds 21,162 of 22,264 Acts. DATASET.md's "1,568
Acts" is the central legislation file alone (848 in force + 710 repealed + 10 spent), not the whole set.

### Duplicate chunk ids: the dead Kerala vectors look like second copies of live chunks

**Established.** The parquet has **zero** duplicated `chunk_id`s in 33.7M rows, and `acts_india` has
zero in 1,098,577 points, so the duplicates in the vector collections were introduced by loading.
Section 8 already found 4,871 on the Supreme Court set. In the first 200,000 `legal_corpus_v2` points,
697 chunk ids sit on two or more points, across at least 11 courts (Jharkhand 378, Kerala 292,
Punjab and Haryana 168, Rajasthan 168, Himachal Pradesh 138, Karnataka 124, J&K 76). This is not a
Kerala-only or Supreme-Court-only pattern.

**Established, in the 100,000-point Kerala slice.** 511 chunk ids sit on two or more points (1,024
points). **No group has two dead members**: 211 are live+live, 298 are dead+live, 2 are dead+live+live.
Dead points are 5.5 times as likely as live ones to have a twin inside the slice (4.3% against 0.8%).
In a sample of 3,000 dead points, the text is identical to the parquet text of the same chunk id in
99.4% of the 2,970 found.

**Established, the Kerala count, exactly** (from `scan/kerala_v2.tsv`, which holds the id and chunk id of
all 3,125,018 Kerala points, against the Kerala parquet's 2,777,738 distinct ids; `kfix_dup_*` scripts).
Qdrant's Kerala points are 2,687,921 distinct chunk ids on 3,125,018 points:

| Group size | Chunk ids | Points |
|---|---:|---:|
| 1 | 2,310,291 | 2,310,291 |
| 2 | 320,127 | 640,254 |
| 3 | 55,539 | 166,617 |
| 4 | 1,964 | 7,856 |

**437,097 points are extra copies (14.0% of Kerala's points)**, on 377,630 chunk ids. They break down as
217,688 dead copies and 219,409 live copies (57,581 of them in groups that also hold a dead copy, 161,828 in groups of live points only). The other 78 dead points have no `court` label and sit in the no-court scan, outside this count. Reconciliation with the parquet, to the point:

> 2,777,738 parquet ids − 117,119 parquet-only + 27,302 Qdrant-only = 2,687,921 distinct ids in Qdrant;
> 2,687,921 + 437,097 duplicates = **3,125,018**.

So duplicates account for more than the whole per-court excess (347,280): they exceed it by 89,817, which
is the net of two real differences. **117,119 parquet chunks (111,804 whole cases) are not in Qdrant**
(4.2% of the parquet's Kerala ids), and **27,302 Qdrant chunks (9,276 whole cases) are not in the
parquet**. Only 997 of those 117,119 missing chunks lie inside a case Qdrant otherwise holds. This
corrects my earlier reading ("about 99% overlap, so the two datasets are the same, section 8's
cross-check is sound"): the overlap is 95.8% of the parquet and 99.0% of Qdrant, and the difference is
whole cases on both sides, the same shape as the Supreme Court's 10,112 and 5,153 in section 8. It is a
snapshot mismatch worth a line on the coverage page, not noise. It does not make section 8's comparison
one between unrelated datasets.

**Established: every dead point has a live twin, and none has two dead members.** All 217,766 flagged
points sit in a duplicate group with at least one unflagged point (217,688 in the labelled Kerala scan,
the other 78, which have no `court` label, in the no-court scan under a different id). Groups containing
a dead point: 162,071 pairs, 53,653 triples and 1,964 quadruples, **each with exactly one dead member**.
The 159,942 groups with no dead member are live-on-live duplicates. That is the whole of the "inferred"
claim in the earlier draft of this section, now exact for Kerala: the "dead" vectors are valid embeddings
from another model (section 17) attached to **second copies** of chunks whose first copy is healthy.

**Established: duplicates carry identical text.** All **697 of 697** duplicated chunk-id groups in the
first 200,000 `legal_corpus_v2` points (695 pairs, 2 triples, 11 or more courts) hold byte-identical
`text`, and every other payload field (`case_id`, `title`, `pdf_url`, offsets, pages, year and the rest)
is identical as well. So are **511 of 511** groups in the Kerala slice, including the 298 dead+live
pairs. **Corrected 4 Nov 2026:** the first version of this slice check was
vacuous. It read the slice file, which stores only `chunk_id`, `case_id` and `court` (no text), so it compared
empty values and proved nothing. It was redone from full payloads fetched from the original for all 26,105 slice
points that sit in a duplicated chunk id (1,306 read-only requests, slowest 0.23 s, every text non-empty): **511 of
511 groups hold byte-identical text (211 live+live, 300 dead+live including the three-member groups) and no other
payload field differs inside any group.** The conclusion stands; the evidence for it now exists. The 697-group check
above was never affected (its payloads came from the original with text). Whitespace-only and real-content differences: none in either. A record fetched by either point
id is the same record, so **verifier check 3 cannot be fooled by which copy `get_record` returns**
(it matches quotes against that text). The duplicate risk that remains is the one in section 8 (two
source ids for one passage), a presentation problem, not a verification one. **Limits:** the 697 are the
first 200,000 v2 points only; v1, the rest of v2 and the Supreme Court's 4,871 duplicates were not
text-compared.

**Estimated: duplication across `legal_corpus_v2`.** Two copies sit at unrelated random point ids, so a
sample of the first 200,000 points (1.69% of the collection) contains both copies of a pair with
probability 1.69% squared; the in-sample pair count therefore scales as 1 / 0.000286. The estimator is
checked against the exact Kerala count: it predicts 142.6 Kerala groups in the sample and 146 were seen.
It gives about **2.45 million extra points in v2, or roughly 21% of its 11.8M (±4% from sampling alone)**.
By court prefix (points in v2 are the estimated total, the share is of that court): Jharkhand about 54%,
J&K 53%, Himachal Pradesh 48%, Punjab and Haryana 23%, Rajasthan 22%, Kerala 16% (exact: 14.0%),
Karnataka 14%, Orissa 8%, Madhya Pradesh 5%, Supreme Court 3% (3 groups seen; section 8's exact count
is 4,871 chunk ids on 371,159 points). No duplicate was seen in the sample for Delhi (829 sample points),
Bombay (HCBM, 2,412), Madras (HCMA and HCMD, 2,261), Telangana (HBHC, 1,917) or Gujarat (1,071); with the
sample's reach that bounds each below roughly 10,000 extra points (95%), which is weak for a court as
small as Delhi's. Of the three launch High Courts, Kerala is duplicated at 14.0%; Bombay and Telangana
showed none in the sample. **v1 (19.6M points) was not sampled at all**, so no figure for it exists, and the
total across both collections is **not** known. It needs the scan.

**What this does to the dead-vector story.** The re-embed (A123, about $16.36) repaired 217,766 points
whose chunk already had a healthy copy. It was not harmful, but with a live twin present it is also not
needed to find those chunks, and it turns a dead copy, which rarely ranked, into a live copy that now ranks
beside its twin. **Serving Kerala from one point per chunk id, the healthy one, makes the repaired
collection unnecessary** and needs no model call. That is a serving decision for the owner (dedup in the
pipeline, section 8); nothing was changed.

**Overall, the premise needs one correction.** Qdrant has **fewer** points than the parquet (31.42M
against 32.57M), not more; the difference is the Supreme Court's 742,066 non-English chunks (1,113,313
in the parquet against 371,159 English in Qdrant) and smaller per-court gaps. Kerala is the court where
Qdrant is larger.

## 19. Is law missing from the search index? Per-court gap between the parquet and Qdrant

**4 Nov 2026 (overnight lane A).** **Measured**, from an exhaustive read-only scroll of `legal_corpus_v2` (11,823,753 points) and `legal_corpus_v1` (19,595,718 points) and all 26 judgment parquet files (32,572,660 distinct chunk ids). A chunk counts as indexed if its id is in EITHER collection. Nothing was written to any Qdrant; no embedding, no cost. The scan read 11,823,753 points of legal_corpus_v2 (its count was 11,823,753), 19,595,718 points of legal_corpus_v1 (its count was 19,595,718). The scan used the night's rule (60 s timeout, a checkpoint every page, 30 s back-off and retry, hard stop after 5 consecutive failures): 0 failed or slow requests were logged and retried.

### What was found

- **4,982,402 of 32,572,660 parquet chunks (15.30%) are in no Qdrant collection** (Measured). **4,945,000 of them (99%) sit in 3,216,075 WHOLE cases that Qdrant holds no chunk of at all** (invisible law); 37,402 are scattered chunks of 26,429 cases that are otherwise present (findable but incomplete). **Whole missing cases dominate.**
- Of the parquet-only chunks, 4,240,336 are English and 742,066 are not (the dataset card says English only; the non-English chunks of Supreme Court of India are the known exclusion, section 8). English parquet-only chunks are **13.32%** of all English parquet chunks.
- The reverse: 218,239 chunk ids are in Qdrant and not in the parquet.

### Per court (all id prefixes of a court summed; Measured)

| Court | Parquet chunks | In Qdrant | Overlap | Parquet-only | in whole missing cases | in partial cases | whole cases missing | English parquet-only | Qdrant-only |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| rajasthan | 2,676,195 | 1,076,467 | 40.2% | **1,599,728** | 1,596,831 | 2,897 | 732,511 | 1,599,728 | 516 |
| punjab-and-haryana | 1,845,344 | 929,325 | 50.4% | **916,019** | 906,975 | 9,044 | 652,833 | 916,019 | 12,012 |
| supreme-court | 1,113,313 | 361,135 | 32.4% | **752,178** | 751,976 | 202 | 351,665 | 10,112 | 5,153 |
| orissa | 872,833 | 463,256 | 53.1% | **409,577** | 409,441 | 136 | 408,974 | 409,577 | 18,478 |
| madhya-pradesh | 970,908 | 726,428 | 74.8% | **244,480** | 244,378 | 102 | 243,679 | 244,480 | 344 |
| calcutta | 535,453 | 318,399 | 59.5% | **217,054** | 217,053 | 1 | 139,586 | 217,054 | 9,444 |
| jharkhand | 777,734 | 599,973 | 77.1% | **177,761** | 177,748 | 13 | 176,690 | 177,761 | 13,209 |
| uttarakhand | 307,144 | 172,144 | 56.0% | **135,000** | 134,987 | 13 | 79,117 | 135,000 | 60 |
| karnataka | 1,471,128 | 1,351,996 | 91.9% | **119,132** | 105,639 | 13,493 | 102,616 | 119,132 | 6,517 |
| kerala | 2,777,738 | 2,661,397 | 95.8% | **116,341** | 115,343 | 998 | 111,528 | 116,341 | 27,277 |
| allahabad | 2,007,927 | 1,913,371 | 95.3% | **94,556** | 94,370 | 186 | 67,857 | 94,556 | 13,541 |
| himachal-pradesh | 619,919 | 556,295 | 89.7% | **63,624** | 63,364 | 260 | 62,970 | 63,624 | 569 |
| jammu-and-kashmir | 181,221 | 121,760 | 67.2% | **59,461** | 59,396 | 65 | 59,164 | 59,461 | 108 |
| tripura | 112,120 | 69,817 | 62.3% | **42,303** | 42,272 | 31 | 10,569 | 42,303 | 170 |
| sikkim | 11,389 | 1,398 | 12.3% | **9,991** | 9,991 | 0 | 1,757 | 9,991 | 9 |
| gujarat | 1,400,249 | 1,390,771 | 99.3% | **9,478** | 809 | 8,669 | 682 | 9,478 | 29,811 |
| manipur | 39,507 | 30,701 | 77.7% | **8,806** | 8,806 | 0 | 8,730 | 8,806 | 136 |
| meghalaya | 25,558 | 20,780 | 81.3% | **4,778** | 4,683 | 95 | 4,669 | 4,778 | 375 |
| telangana | 2,732,387 | 2,730,642 | 99.9% | **1,745** | 820 | 925 | 363 | 1,745 | 10,460 |
| chhattisgarh | 1,744,438 | 1,744,285 | 100.0% | **153** | 13 | 140 | 13 | 153 | 13,148 |
| bombay | 2,788,384 | 2,788,309 | 100.0% | **75** | 36 | 39 | 36 | 75 | 36,613 |
| gauhati | 663,094 | 663,046 | 100.0% | **48** | 34 | 14 | 31 | 48 | 1,318 |
| madras | 2,610,596 | 2,610,555 | 100.0% | **41** | 25 | 16 | 25 | 41 | 2,223 |
| patna | 2,562,269 | 2,562,239 | 100.0% | **30** | 0 | 30 | 0 | 30 | 945 |
| delhi | 1,064,459 | 1,064,431 | 100.0% | **28** | 10 | 18 | 10 | 28 | 15,512 |
| andhra-pradesh | 661,353 | 661,338 | 100.0% | **15** | 0 | 15 | 0 | 15 | 291 |
| **Total** | 32,572,660 | 27,590,258 | 84.7% | **4,982,402** | 4,945,000 | 37,402 | 3,216,075 | 4,240,336 | 218,239 |

### The launch courts (CLAUDE.md section 1)

The gate binds on the **whole-missing-case** column (a case Qdrant holds no chunk of at all is invisible law). The scattered-chunk column is the other shape (a findable case that is incomplete); it is reported beside it and does not bind.

| Court | English cases | **Whole English cases in no collection** | **Share of cases (binds)** | English chunks | English chunks scattered in present cases | Share of chunks (reported) | All English chunks in no collection |
|---|---:|---:|---:|---:|---:|---:|---:|
| Bombay | 1,578,864 | 36 | **0.00%** | 2,788,384 | 39 | 0.00% | 75 (0.00%) |
| Telangana | 1,005,147 | 363 | **0.04%** | 2,732,387 | 925 | 0.03% | 1,745 (0.06%) |
| Kerala | 1,018,715 | 111,528 | **10.95%** | 2,777,738 | 998 | 0.04% | 116,341 (4.19%) |
| Supreme Court of India | 35,596 | 734 | **2.06%** | 371,247 | 202 | 0.05% | 10,112 (2.72%) |
| All courts | 15,692,122 | 2,865,144 | **18.26%** | 31,830,594 | 37,402 | 0.12% | 4,240,336 (13.32%) |

### Spot-check: 20 wholly missing English cases read from the parquet (Measured; samples drawn at random, 3 each from Kerala, Bombay and Telangana, 2 Supreme Court of India, the rest across other courts)

Classes: {'substantive English': 20}. **Absence re-confirmed directly in Qdrant (an indexed `case_id` count on both collections): 20 of 20 have 0 chunks.**

| Case id | Chunks | Languages | Median chars | Chunks under 200 chars | Class | Opens with |
|---|---:|---|---:|---:|---|---|
| `KLHC010085532010` | 1 | {'en': 1} | 1817 | 0 | substantive English | Case: Bail Appl./8431/2010 of K.ARUN KUMAR Vs STATE OF KERALA (2011) Court: High Court of Kerala Section: BODY |
| `KLHC010314332010` | 1 | {'en': 1} | 1021 | 0 | substantive English | Case: MACA/1904/2010 of MOHANAN Vs KANNAN AND OTHERS (2018) Court: High Court of Kerala Section: BODY [TITLE]  |
| `KLHC010021732016` | 1 | {'en': 1} | 1898 | 0 | substantive English | Case: Bail Appl./1992/2016 of SUBHASH Vs STATE OF KERALA (2016) Court: High Court of Kerala Section: BODY [TIT |
| `HCBM040231782008` | 1 | {'en': 1} | 3922 | 0 | substantive English | Case: LPA/378/2008 of REKHA MUKUNDRAO BHAGWAT Vs STATE OF MAH. THR. SECRETAY AND 2 ORS (2009) Court: Bombay Hi |
| `HCBM040143812004` | 1 | {'en': 1} | 1073 | 0 | substantive English | Case: CA/1816/2004 of SAU. YASHREE YASHODHAN SADAPHAL.. Vs STATE OF MAH and OTHERS. (2009) Court: Bombay High  |
| `HCBM040052472009` | 1 | {'en': 1} | 1657 | 0 | substantive English | Case: CAW/574/2009 of SHIVNANDA W/O BHAGWANDAS MESHRAM and ANR. Vs VATSALABAI WD/O PARASRAM DHONGDE and OR...  |
| `HBHC010002082004` | 3 | {'en': 3} | 1566 | 0 | substantive English | Case: CMA/2335/2004 of Cheekumalla Salman Raju Vs Vijay Ramingle (2015) Court: High Court for State of Telanga |
| `HBHC010384082013` | 3 | {'en': 3} | 2101 | 0 | substantive English | Case: CC/508/2013 of P. Mariya Dass Vs Sri A.K.Khan IPS, (2015) Court: High Court for State of Telangana Secti |
| `HBHC010454162014` | 2 | {'en': 2} | 3062 | 0 | substantive English | Case: CC/824/2014 of Sri Venkateswara Saw Mill, Vs Sri Nagarjuna Reddy (2015) Court: High Court for State of T |
| `2019_INSC_1284` | 20 | {'ben': 3, 'pun': 5, 'en': 7, 'hin': 5} | 3720 | 0 | substantive English | Case: NASIMA NAQI versus TODI TEA COMPANY LTD. AND ORS [[2019] 17 S.C.R. 1048] (2019) Section: PARAGRAPH �িতেব |
| `2021_INSC_66` | 15 | {'en': 6, 'pun': 4, 'hin': 5} | 3548 | 0 | substantive English | Case: BOLORAM BORDOLOI versus LAKHIMI GAOLIA BANK & ORS. [[2021] 1 S.C.R. 858] (2021) Section: BODY 858 SUPREM |
| `RJHC020646992014` | 1 | {'en': 1} | 2511 | 0 | substantive English | Case: CRLMP/3302/2014 of GIRRAJ MEENA AND ORS Vs STATE OF RAJASTHAN THROUGH PP (2015) Court: High Court Of Raj |
| `RJHC020037652020` | 2 | {'en': 2} | 3848 | 0 | substantive English | Case: CRLMA/19/2020 of AVININDRA SINGH BHATI S/O SHRI RAGHUNATH SINGH BHATI Vs NARAYAN SINGH S/O GOVIND SI...  |
| `RJHC020684362015` | 5 | {'en': 5} | 3964 | 0 | substantive English | Case: CW/6799/2015 of LAHRI RAM MEENA Vs U O I AND ORS (2018) Court: High Court Of Rajasthan Section: PARAGRAP |
| `TRHC010026122019` | 1 | {'en': 1} | 1528 | 0 | substantive English | Case: WA/190/2019 of SANIT DEBROY Vs THE STATE OF TRIPURA AND ORS. (2020) Court: High Court of Tripura Section |
| `ODHC010406782018` | 1 | {'en': 1} | 596 | 0 | substantive English | Case: CRLMA/200/2018 of RAJAT KUMAR BEHERA Vs STATE OF ORISSA (2019) Court: Orissa High Court Section: BODY 02 |
| `HPHC010485892023` | 1 | {'en': 1} | 1051 | 0 | substantive English | Case: CRMPM/3021/2023 of CHAMAN LAL Vs STATE OF HP (2024) Court: High Court of Himachal Pradesh Section: BODY  |
| `UPHC020528792024` | 1 | {'en': 1} | 2554 | 0 | substantive English | Case: /8443/2024 of AMIT KUMAR Vs STATE OF U.P. THRU. PRIN. SECY. HOME LKO. (2024) Court: Allahabad High Court |
| `KAHC010172562015` | 1 | {'en': 1} | 1918 | 0 | substantive English | Case: WP/5874/2015 of M/S. HOTEL PRANAM Vs THE STATE OF KARNATAKA (2017) Court: High Court of Karnataka Sectio |
| `MPHC030211692020` | 1 | {'en': 1} | 1024 | 0 | substantive English | Case: MCRC/42863/2020 of RAM BHARAT SEN Vs THE STATE OF MADHYA PRADESH (2020) Court: High Court of Madhya Prad |

### Qdrant-wide `court` label rate (the figure section 18 left pending; Measured on the whole originals)

- `legal_corpus_v2`: 11,823,753 points: usual 11,742,541 (99.31%), missing 75,786 (0.64%), alias 5,221 (0.04%), other_court 205 (0.00%)
- `legal_corpus_v1`: 19,595,718 points: usual 19,412,246 (99.06%), missing 125,741 (0.64%), alias 57,519 (0.29%), other_court 212 (0.00%)

### Where the court came from (CLAUDE.md section 6)

**The court of every row was taken from the chunk id, not from the `court` label**, on both sides: chunk id prefix (core/court_ids.json) for the parquet AND for Qdrant; the payload `court` label is not used to assign a court. A label-based comparison would silently drop the rows with no label, which are the rows most likely to be absent, and would understate the gap. Ids that name no known court were kept, not dropped: 0 parquet rows and 0 points of `legal_corpus_v2`, 0 points of `legal_corpus_v1` (they are the `?` row of the court counts). Qdrant points with an empty `court` label (Measured; the rows a label-based comparison would have lost on the Qdrant side): `legal_corpus_v2` 75,786, `legal_corpus_v1` 125,741. The parquet `court` label was not read at all; the 0.58% missing-label rate for the parquet is section 6's figure, not re-measured here.

### Verdict

By a rule that binds on whole missing cases (owner, 4 Nov 2026; the 1% threshold is my number, not the owner's): **a defect for the launch gate if whole English cases absent from Qdrant are 1% or more of a launch court's English cases, or of all English cases.** Whole missing cases: Bombay 0.00% (36 of 1,578,864 cases); Telangana 0.04% (363 of 1,005,147 cases); Kerala 10.95% (111,528 of 1,018,715 cases); Supreme Court of India 2.06% (734 of 35,596 cases); All courts 18.26% (2,865,144 of 15,692,122 cases). Scattered-chunk rate beside it (reported, does not bind): Bombay 0.00%; Telangana 0.03%; Kerala 0.04%; Supreme Court of India 0.05%; All courts 0.12%.

**Which condition tripped: whole missing cases TRIPPED in Kerala, Supreme Court of India, All courts; the scattered-chunk rate did not reach the threshold anywhere (it does not bind).** **This is a coverage DEFECT that belongs in the launch gate.** The spot-check classes above say whether the missing cases are real judgments (substantive English) or rows left out on purpose; **read the table before trusting the rule: its classes are automatic (language and chunk length only) and were not read by a person.**

### What this does not cover

- Chunk presence is by id. A chunk present with the wrong text or an empty vector counts as present. Nothing here checks vectors.
- The parquet is the reference: a chunk missing from the parquet but present in Qdrant is reported, not judged. The case key is the chunk id without its trailing `_<n>`, which matched the `case_id` in every parquet row measured earlier (section 18).
- The overall `court` label counts treat an id that names no known court as unclassifiable. The classification of a missing case as real or placeholder is from language and length only for the ones not spot-checked.
- The hashes are 64-bit (a collision among 64M ids has probability under 1e-4); not verified beyond that.

## 20. Which central Acts the corpus actually holds (inventory, 4 Nov 2026)

**Measured, read-only, no embeddings, no model calls, no spend** (`scan/central_acts_inventory.py`). CrPC 1973 turned up missing by
accident (nine lookups returned nothing). This is the proactive version: every central Act, in three places, and the most-practised
statutes checked against all three. Results: `~/qdrant-kanoon/central_acts/inventory.json`.

**Totals. The three layers agree exactly: 1,568 central Acts.** The source parquet (`in_central_legislation.parquet`) holds 1,568
Acts in 74,484 chunks; `acts_india` holds the same 1,568 in 74,509 points (25 more points, no more Acts); the served `kanoon_v1`
holds the same 1,568 in 74,484 points. **Nothing in the central file is missing from what is served: there is no central-Act
indexing gap.** DATASET.md's "848" is the in-force count only: **848 in force + 710 repealed (`IND_REP_`) + 10 spent = 1,568.**
The 74,509 points are all 1,568 Acts; they are not 848 Acts. Whether 1,568 is *complete against India Code* is not verified from
here (that needs the live site).

**The checklist (84 statutes the owner named or that are most practised): 78 present and served, 6 absent from the central file and from
the served collection. Corrected 4 Nov 2026: five of the six are an INDEXING problem, one an ACQUISITION problem.** A first draft of this
table called all six acquisition; it had looked for them in `acts_india` and the source files as central Acts and stopped at "not central". The
text exists for five, filed under States, and is **staged in full in `acts_noncentral_v1`** (the A133 state-Act staging collection, every
chunk of every copy present: 10,696 + 819 + 396 + 525 + 402) but **not promoted into the served `kanoon_v1`**. That is the A133 promotion work,
not a purchase or an extraction.

| Absent from the served collection | What exists | Class |
|---|---|---|
| Code of Criminal Procedure, 1973 (Act 2 of 1974) | **14 state- and UT-tagged copies**, 764 chunks each, in 8 files (Chandigarh 5, Chhattisgarh 3, Dadra and Nagar Haveli, Maharashtra, Punjab, Rajasthan, Tripura, Uttar Pradesh: 1 each), all in `acts_india` and staged in `acts_noncentral_v1`. **`IND_state_6796` (Dadra and Nagar Haveli) is the central copy**: the owner's earlier repo records it as "the Central CrPC 1973 whose category was corrected to central (not a State copy)" (`vaquill-local/docs/W9.md` line 38, `MISSING-SECTIONS.md` line 434); in `acts_india` it still carries `category: state` and `act_status: in_force`, and as the Code repealed by the BNSS it should read repealed | **Indexing** (promote one copy, `IND_state_6796`, with its category corrected) |
| Consumer Protection Act, 1986 | 7 state-tagged copies, 75 chunks each (Chandigarh, Gujarat, Jharkhand, Madhya Pradesh, Manipur, Odisha, Rajasthan) | **Indexing**. Repealed by the 2019 Act, which IS served; the 1986 Act governs older disputes |
| Payment of Gratuity Act, 1972 | 11 state-tagged copies, 36 chunks each | **Indexing** |
| Employees' Compensation (Workmen's Compensation) Act, 1923 | 3 state-tagged copies, 134 chunks each (Haryana, Punjab, Rajasthan) | **Indexing** |
| Constitution of India | 9 state- and UT-tagged copies, 91 chunks each (Andaman and Nicobar 2, Chandigarh 5, Puducherry 1, Rajasthan 1) | **Indexing, with one check owed:** that 91 chunks is the whole Constitution. Not verified; the identical count across nine copies says they are one text, not that it is complete |
| **Indian Trusts Act, 1882** | **None, in any of the 49 legislation and regulation files** | **Acquisition**: the only one genuinely absent from the data |

The Factories Act 1948, Minimum Wages Act 1948, Payment of Wages Act 1936 and Maternity Benefit Act 1961 are in the data as repealed (by the labour
codes), so the central file does list Acts those codes repealed; Gratuity and Employees' Compensation, which the Code on Social Security also
subsumes, are not among them. **Promotion is not a bare copy:** the 14 CrPC copies share one title, so a promotion that copies all of them serves the same text
fourteen times, and a state copy may carry a state's amendments. The owner's earlier repo promoted exactly one (`IND_state_6796`) for that reason. Not decided here.

**Present and served (78):** IPC 1860 (repealed, 774 chunks), Evidence Act 1872 (repealed, 274), CPC 1908, BNS, BNSS and BSA 2023
(469, 827, 210 chunks), Contract Act, Sale of Goods, Partnership, LLP, Companies Act 2013 and 1956 (1956 repealed), Arbitration and
Conciliation, Negotiable Instruments, Limitation, Specific Relief, Transfer of Property, Registration, Stamp, Easements, IBC,
SARFAESI, RDDBFI, Competition, IT Act, Copyright, Patents, Trade Marks, Consumer Protection 2019, RERA, RTI, FEMA, PMLA,
Prevention of Corruption, NDPS, Arms, Motor Vehicles, POCSO, Domestic Violence, Dowry Prohibition, Juvenile Justice, SC/ST
Atrocities, Succession, the Hindu statutes (Marriage, Succession, Minority and Guardianship, Adoptions and Maintenance), the Muslim
statutes (Shariat Application, Dissolution of Muslim Marriages, Muslim Women), Special Marriage, Guardians and Wards, Christian
Marriage, Parsi Marriage and Divorce, Family Courts, Income-tax Act 1961 (2,650 chunks), CGST and IGST, Customs, Central Excise, the
four labour codes, Industrial Disputes, Factories (repealed), EPF, Minimum Wages (repealed), Payment of Wages (repealed), Maternity
Benefit (repealed), POSH, Land Acquisition 2013, Environment Protection, Representation of the People, Advocates, Contempt of
Courts, Legal Services Authorities, Protection of Human Rights. Status is as the data records it; `act_status` is a default outside
the `IND_REP_` ids (section 18), so "in force" for any Act here is not a determination.

**What the table does not show.** A present Act can still be incomplete (section gaps are a separate audit row: 6,814 Acts with
missing sections, 45,963 garbled), and this lists Acts, not sections. The checklist is the owner's list, not a legal census.

## 21. Embedding health, per court (4 Nov 2026): no court besides Kerala holds vectors unrelated to its text, and the corpus is a mix of three models

**Measured.** One job (`scan/embedding_health.py`), every court. A random sample of **59,454 points** from the two original
collections (48 court-by-collection groups, 1,100 to 1,800 points each, whole groups read where they were smaller, plus a
2,000-point sample of the points that carry no `court` label), each stored text re-embedded with `voyage-4` as a document and
compared by cosine with the vector already stored; the existing dead-vector detector scored the same stored vectors. The court is the id prefix,
not the label. Group sizes are exact (the section 19 scan). Read-only on `legal_corpus_v1` / `v2` (1,460 reads, slowest 16 s,
no hard stop); nothing written anywhere. **Spend: 53,760,590 tokens = $3.23** at list price (the sample was priced locally,
exactly, before the run: 53,651,624 tokens, $3.22; the rest is a 50-chunk preflight and the identification step below), every
request in `token_ledger.jsonl` under the tag `health:`, cap $6.00 never approached. Preflight: 50 of 50 chunks of a court known
to be `voyage-4` reproduced at cosine 0.9999 or better, so the method (document `input_type`, 1,024 dimensions, the text as stored) is right.

**Why the test is three-way, not "near 1.0 is correct".** The stored vectors are not all `voyage-4`'s. A re-embed reads as one of:
cosine **0.99 or more** (the stored vector is `voyage-4`'s own), **0.50 to 0.99** (the vector belongs to this text but another
model of the family made it), **below 0.50** (unrelated to the text). Lines, with the evidence for each: dead Kerala vectors
re-embed at -0.138 to +0.133 (217,766 chunks, A123); other-model chunks at **0.672 to 0.972** (41,692 in this run, median 0.952,
0.1th percentile 0.895). Nothing observed sits between 0.14 and 0.67. 23 chunks first read as an unexplained middle (0.67 to
0.84, 21 of them Chhattisgarh); each was re-embedded under `voyage-4-lite` and `-large` and **23 of 23 reproduced at 0.996 or more
under one of them**, so they are ordinary other-model chunks and the earlier lowest value (0.839) was a small-sample bound.

### Finding 1: only Kerala has vectors unrelated to its text

| | Sampled | Unrelated to text (cosine below 0.5) |
|---|---:|---:|
| High Court of Kerala, `legal_corpus_v2` | 1,800 | **102 (5.67%, 95% interval 4.69 to 6.83)** |
| **Every other group (47 groups plus the no-label points)** | **57,654** | **0** |

For the 47 groups with 1,100 or more points sampled, the 95% upper bound on a defect rate is **0.21% to 0.35%** per group. In points
that is at most 6,017 for the largest (Bombay, collection 1) and 69,533 summed over all the courts, which at `voyage-4` batch rates
is **$2.54 at most**, against **$0 found**. **The re-embed adds nothing to A141's $137.57 batch; the bound is $140.11.**
Kerala's 102 were already handled (A123: re-embedded into `kerala_v2_fix`, about $16, and every dead point has a live twin, A126).
Clean courts, so stated: **Andhra Pradesh, Patna, Chhattisgarh, Delhi, Gauhati, Gujarat, Telangana, Bombay, Madras (both),
Himachal Pradesh, the Supreme Court, Jharkhand, Jammu and Kashmir, Karnataka, Meghalaya, Manipur, Madhya Pradesh, Orissa, Punjab
and Haryana, Rajasthan, Sikkim, Tripura, Uttarakhand, Allahabad, Calcutta (all four prefixes)**, and the unlabelled points. Small
groups carry wide bounds (Sikkim 124 sampled, bound 3.0%; collection-2 Tripura 5 and Calcutta Original 4 points, read whole).

**The positive control, and its limit.** The Kerala sample finds 5.67% unrelated against 6.97% in the full scan (217,688 of
3,125,018): 102 observed against 125 expected, about 2.2 standard deviations low. The random-offset sampling therefore
under-counts a defect like Kerala's by about a fifth. That does not change zero versus not-zero; it means a bound above should be
read as roughly 25% higher for a defect shaped like Kerala's. Not diagnosed (the ids of dead points may cluster).

### Finding 2: the detector saw all of it, and false-alarms on long chunks

On the 59,454 stored vectors the detector flagged 116: all **102** Kerala flags are the 102 unrelated chunks, **no unrelated vector was missed (0
of 59,454)**, and the other 14 are healthy vectors flagged (13 Supreme Court chunks, 12 of them 3,000 characters or more, and 1 Chhattisgarh). So the
failure that "the detector cannot see", a vector from another chunk that looks healthy, **did not show up**: none of the stored vectors that
the re-embed calls unrelated scored healthy. Length-stratified (chunk length in characters):

| Length | Kerala: sampled / flagged (rate) | All other groups: sampled / flagged (rate) |
|---|---|---|
| under 500 | 4 / 0 | 661 / 0 (0%) |
| 500 to 1,499 | 105 / 2 (1.9%) | 7,591 / 0 (0%) |
| 1,500 to 2,999 | 321 / 25 (7.8%) | 14,417 / 1 (0.01%) |
| 3,000 or more | 1,370 / 75 (5.5%) | 34,985 / 13 (0.04%; 12 of them Supreme Court, 12 of 884 = 1.4%) |

The false-alarm rate on long chunks is the 1% of section 13, concentrated in one court; outside the Supreme Court it is 1 in 34,101.
**Not tested:** a vector belonging to a *neighbouring* chunk of the same case would read well above 0.5 and could sit in the other-model
band. The other-model band is tight (0.1th percentile 0.895) and the only 23 chunks below 0.84 were all identified as lite or large, so any
such population is small, but between 0.84 and 0.9 it is not excluded by this run.

### Finding 3: the model mix per court (a finding in its own right)

**Weighted by points, 47.7% of the corpus's stored vectors are `voyage-4`'s own and 52.3% were made by `voyage-4-lite` or `-large`**
(collection 1: 55.0% own; collection 2: 35.7% own; 31,419,471 points). The 73% of section 13 is the share of an equal-weight
sample of 2,640 chunks across court groups (this run, unweighted: 70.0%); weighted by how many points each group holds, it is 52%. The model
is a property of the ingestion batch, not the court, and groups fall into three kinds:

- **Uniformly `voyage-4`** (97% or more own): Gauhati, Gujarat, Telangana, Bombay, Madras (both prefixes) and Himachal Pradesh in collection 1, and Calcutta Original's 4 points in
  collection 2 (10.5M points).
- **Uniformly another model** (3% or less own): 29 groups, 13.1M points. Patna, Chhattisgarh, Andhra Pradesh, Supreme Court, Jharkhand,
  Jammu and Kashmir, Karnataka, Rajasthan, Sikkim and Calcutta in both collections, and Allahabad, Tripura, Uttarakhand in collection 1, among them.
- **Mixed inside the group** (7.8M points): Kerala v2 (90% own), Punjab and Haryana v2 (15%), Delhi v1 (17%), Madhya Pradesh v2 (94%),
  Orissa v2 (89%), Manipur v2 (93%), Meghalaya v2 (93%), Allahabad v2 (17%), Uttarakhand v2 (32%), Tripura v2 (60%), Andhra Pradesh v1 (3%).

| Court | Prefix | Points | `voyage-4` own, collection 1 | collection 2 |
|---|---|---:|---:|---:|
| Andhra Pradesh | APHC | 1,064,243 | 3% | 0% |
| Patna | BRHC | 2,682,782 | 0% | 0% |
| Chhattisgarh | CGHC | 1,824,522 | 0% | 0% |
| Delhi | DLHC | 1,127,337 | 17% | 0% |
| Gauhati | GAHC | 693,391 | 100% | 0% |
| Gujarat | GJHC | 1,486,348 | 100% | 0% |
| Telangana | HBHC | 2,857,444 | 100% | 0% |
| Bombay | HCBM | 2,963,323 | 100% | 0% |
| Madras | HCMA, HCMD | 2,750,364 | 100% | 0% |
| Himachal Pradesh | HPHC | 781,765 | 100% | 0% |
| Supreme Court | INSC | 371,159 | | 0% |
| Jharkhand | JHHC | 1,250,333 | | 0% |
| Jammu and Kashmir | JKHC | 246,948 | | 0% |
| Karnataka | KAHC | 1,570,097 | | 0% |
| Kerala | KLHC | 3,125,877 | | 90% |
| Meghalaya | MLHC | 22,221 | | 93% |
| Manipur | MNHC | 32,262 | | 93% |
| Madhya Pradesh | MPHC | 767,298 | | 94% |
| Orissa | ODHC | 507,767 | | 89% |
| Punjab and Haryana | PHHC | 1,268,090 | | 15% |
| Rajasthan | RJHC | 1,358,039 | | 0% |
| Sikkim | SKHC | 2,704 | 0% | 1% |
| Tripura | TRHC | 139,979 | 0% | 60% |
| Uttarakhand | UKHC | 266,589 | 0% | 32% |
| Allahabad | UPHC | 1,930,220 | 0% | 17% |
| Calcutta | WBCHCA, J, O, P | 328,369 | 0% | 0% (Original: 100% of 4 points) |

**What it would cost to make the corpus uniform.** Re-embedding only the off-model points (about 16.4M, before A126's de-duplication, which lowers it) to
`voyage-4` is about 15.2B tokens: **$912 at standard, $611 at batch rates** (collection 1 about $301 at batch, collection 2 about $309). This is a price and is NOT proposed: the question that matters is the `large` slice (Finding 4), not uniformity.

**What these numbers do settle.** How much of each court sits off the query model, with tight intervals (about 0.2 to 0.4 points at the
uniform ends); that no court but Kerala holds a vector unrelated to its text; and that the other-model vectors are *right for their text*
(identified as reproducing under their own model on the 2,640 chunks of section 13 and on the 23 lowest here; the other 41,669 are inferred from their tight cosine band, not each re-embedded) and sit at a median cosine of 0.95 from `voyage-4`'s own vector of the same text. **What they do not
settle:** whether the mix costs retrieval quality. A cosine between two models' vectors of one text is agreement, not recall. The retrieval evidence is
A128's: for `voyage-4-lite` courts, switching the query to the chunk's own model did *worse* than the `voyage-4` query (hybrid @10 -2.5, dense @10 -1.9
with a court filter, so the `voyage-4` query read lite chunks 1.9 to 2.5 points better); for `voyage-4-large` courts it did better (hybrid @10 +3.8), the one place a
mismatch cost recall; and A136 did not confirm a single `large` query vector as a replacement. A138 caps all of it: the harness is at its ceiling on hybrid.

### Finding 4: the lite versus large split, which sizes the only slice where mismatch measurably costs recall

**Measured 4 Nov 2026, $0.47** (exact local count before the run: 3,826 chunks, 3.32M tokens under each of two models; every request ledgered under
`health:split-`). Up to 100 off-model chunks per group (3,826 in all, drawn at random from the saved sample) were re-embedded under `voyage-4-lite` and under
`voyage-4-large`; a chunk whose stored vector reproduces at cosine 0.99 or more under one of them was made by it. **All 3,826 were identified:
2,890 lite, 936 large, none unidentified** (identified chunks reproduce at 0.9998 or better for lite, 0.9979 or better for large). Section 13's 2,640-chunk split is
now confirmed on 3,826 more and extended to every group.

| By points, collections 1 and 2 together | Share | Points (estimate) |
|---|---:|---:|
| `voyage-4`'s own | **47.7%** | 15.0M |
| `voyage-4-lite` | **19.9%** (95% interval 19.7 to 20.4) | 6.3M |
| `voyage-4-large` | **32.3%** (31.9 to 32.6) | **10.2M** |

The interval is sampling only (it resamples the off-model share and the large share within each group); it does not include the sampler's tendency to under-count,
which the Kerala control shows is about a fifth for a defect shaped like Kerala's, and nothing shows it moves a model share.

**The large slice, by court** (collection and share of the court's own points): Patna (collection 1) 2.56M, 96% of the court; Chhattisgarh (1) 1.76M, 96%; Karnataka (2)
1.54M, 98%; Jharkhand (2) 1.21M, 97%; Andhra Pradesh (1) 0.95M, 90%; Delhi (1) 0.89M, 79%; Himachal Pradesh (2) 0.48M, 62%; Supreme Court (2) 0.37M, 100%;
Jammu and Kashmir (2) 0.23M, 94%; Kerala (2) 0.15M, 5% (50 of 100 off-model Kerala chunks are large, 50 lite). In every other group the sample found no large chunk
(a bound of about 3 in 100 of the off-model chunks), and those groups are uniformly `voyage-4` or uniformly `voyage-4-lite`.

**What this sizes.** For `voyage-4-lite` chunks, 19.9% of the corpus, the measured cost of a `voyage-4` query is nil or better (A128: 1.9 to 2.5 points better
than lite's own query). The slice where a model mismatch measurably costs recall is the `voyage-4-large` slice: **about a third of the corpus, ten million points, concentrated in nine
courts** (A128: +3.8 points on hybrid @10 for matching the model), with the caveats of A138 (the harness is at its ceiling on hybrid) and A136 (a single
`large` query vector did not confirm as a replacement). This is a size, not a measured loss on this slice: A128's 3.8 was measured on 18,399 chunks of 24
courts through the shipped code, not on these ten million points. Nothing here proposes a re-embed.

## 22. Text that is in the record but is not the court's holding: 5 of 79 cited pairs (6%), and the four checks cannot see it (4 Nov 2026, measured)

`CLAUDE.md` §5 says the tick does **not** mean "the quote is the holding, or the AI's summary is right". Until now that was a caveat.
This section is the first measurement of it.

### What was measured

The trust lane's A137 run (`docs/DECISIONS.md` A137): 95 of the 200 questions reach the writer, real `gemini-3.5-flash-lite`, the real
answer prompt, practice-fixture retrieval (1,398 records, fake word-overlap store, re-ranker and gate). 34 drafts ended `answered`, carrying **79
(sentence, cited passage) pairs**. I read the sentence, then the passage it cites, and judged by hand whether the words that say it are the court
speaking. My judgement, from the passage chunk the writer was given, not from the whole judgment, and not an advocate's.

| Reading | Pairs |
|---|---|
| Supported, and the court's own words | 63 |
| Supported but garbled by list-splitting | 8 |
| **In the passage, but not the court's holding** | **5** |
| A model remark stapled to a marker | 1 |
| An empty marker (`[S7]` alone) | 1 |
| An obeyed injection (q192; its own record is the F3 note in `SECURITY-AND-COMPLIANCE.md`) | 1 |

**5 of 79 pairs is 6.3% (95% interval, Wilson: 2.7% to 14.0%). By answer, 3 of the 34 answered drafts (9%) carry at least one.** One run, one model.

### The five

| # | Question | Sentence says (shortened) | Cited | What the passage actually is |
|---|---|---|---|---|
| 1 | q067 (landlord, non-payment of rent) | the Controller "has no option but to direct the tenant to put the landlord in possession" | S1 | **A party's argument.** The landlord's submission, recited by the District Judge, who called it "the correct legal position" and then declined to apply it on the facts. The proposition may be right; the passage does not give it as this court's holding |
| 2 | q067 | the courts below "acted arbitrarily" in refusing ejectment | S1 | **A lower court's holding.** The Judicial Commissioner's decision, recited. The chunk does not show whether the Supreme Court affirmed it |
| 3 | q067 | where the tenant committed default, "the eviction petition filed by the landlords stands allowed" | S6 | **An order on the facts, turned into a rule.** The court's own order disposing of that one appeal. It fits none of the three labels (party's argument, rejected argument, lower court's holding); it is a fourth kind, and it is counted among the five |
| 4 | q088 (preventive detention) | satisfaction that a ground in section 3 exists is a "condition precedent" to the power to detain | S1 | **A rejected argument.** Counsel for a detenu argued it; the passage goes on to say the argument "proceeded on a restricted meaning" and is hard to accept |
| 5 | q091 (dishonoured cheque) | if the drawer fails to pay on notice, section 138 "could be attracted" | S2 | **A lower court's holding.** The Punjab and Haryana High Court's view in *Bandeep Kaur*, which the Supreme Court cites in support of its own conclusion. Not the Supreme Court speaking |

Several of these may be correct statements of law. The defect is attribution: the answer says "the law is X" and the cited words are someone else's.

### Why none of the four checks catches this class

1. **Retrieved for this question:** passes. S1, S2 and S6 were handed to the writer.
2. **Record exists:** passes.
3. **Quotes match:** has nothing to test in four of the five, which carry no quotation marks. The fifth, q088, quotes "satisfaction" and "condition precedent"; check 3 fired and passed, because those words are genuinely in the record (counsel's argument, which the court goes on to reject). That is exactly the case `CLAUDE.md` §5 describes. Section 25 counts how often check 3 fires at all.
4. **Claim supported: measured 5 Nov 2026 with the shipped check, and it passes all five.** The shipped `GeminiDecider.claim_support` (`gemini-3.5-flash-lite`, the real `claim_support.txt`, the eval key), run twice on all 79 pairs with the sentence marker-stripped as `core/verify.py` does and the passage text the writer was given:

   | Category (my hand reading) | Pairs | Real check, first pass |
   |---|---|---|
   | **In the passage, but not the court's holding** | **5** | **5 supports** (5 of 5 again on the second pass) |
   | Model remark stapled to a marker ("In-force status not checked for this Act") | 1 | supports |
   | Obeyed injection (q192) | 1 | supports |
   | Empty marker (`[S7]` alone) | 1 | does not support (removed) |
   | Everything else (63 supported + 8 garbled by list-splitting; the two cannot be separated without re-reading, and this run does not do that) | 71 | 67 supports, 3 partly, 1 does not support |

   Overall 74 supports, 3 partly, 2 does not support; **77 of 79 pass (a "partly" is kept, with its own tick)**. Of the 8 pairs I judged defective, the real check removed 1 (the empty marker) and passed 7. It removed 1 of the 71 others: q056 S6, "No confession made to a police officer shall be proved…" which is section 25 of the Evidence Act quoted verbatim in a judgment that goes on to say it does not apply to a departmental inquiry. I read that as supported; the check read it as not. One pair, and a question for the advocates. The two passes differed on one pair (q026, supports then partly), and both outcomes pass.
   **So the 6.3% passes the shipped check as well:** an argument for a proposition supports that proposition, as predicted. The tick lets all five through.

I found these by reading. No check flagged any of them.

### Not fixed here

Whether a passage is the court's holding or a party's rejected argument is a legal judgement. A model can be asked, but it would be the same kind of reader as the one that
missed it. A classifier would add a fifth check that can be talked round. The instrument is the advocate review. Nothing in the verifier was changed for this.

### How to put the question to an advocate so the answer is comparable to 6%

- **Same unit.** The (sentence, cited passage) pair, not the answer. Same 79 pairs, so the denominator is the same. The pack carries the full passage the writer saw, not my 60-word window.
- **Blind.** My readings and the real check's verdicts are withheld. One closed question per pair: *"Read the sentence, then the passage. In the passage, who is saying the words that support this sentence?"*
  (a) the court, as its own holding or reasoning in this judgment; (b) the statute itself, quoted by the court; (c) a party or counsel; (d) counsel, and the court rejected it; (e) a lower court or tribunal, recited; (f) a different authority the court cites; (g) the court's order on these facts, not a rule; (h) no one: the passage does not say this; (i) cannot tell from this passage alone.
  (b) was added after the real-check run: q056 S6 is section 25 of the Evidence Act reproduced in a judgment, and it is a correct source.
- **Scoring.** (a) and (b) are correct. (c) to (g) are this section's class. (h) is the separate unsupported count (the stapled remark and the empty marker above). (i) is reported beside the figure, never folded in. The figure is pairs in (c) to (g) over pairs reviewed, with an interval, and the by-answer figure beside it.
- **Agreement.** Two advocates on a shared 20 pairs (the 9 flagged ones plus 11 at random, so agreement is stratified toward the hard class and must be reported as such), so a disagreement is visible. A split on (a) against (e) is expected and is itself a finding about how fixed the line is.
- **The pair of numbers.** The advocates' rate, and the real claim check's result on the same pairs (above: it passed 5 of the 5 I flagged). The gap between the two is what the tick lets through. If the advocates' rate differs from 6%, theirs replaces it.
- **The pack.** Built 5 Nov 2026; see `docs/ADVOCATE-REVIEW-PACK.md` for what it holds and how long a row takes.

### Limits

One reader, who is not an advocate; the chunk and not the judgment (so #2 and #5 could read differently with the rest of the judgment); 95 questions on practice-fixture retrieval, where a different corpus slice would change the mix of passages; one model, one run. Measured on the new answer prompt only: the old prompt's pairs were not read for this kind. 8 further pairs are garbled by list-splitting and are not counted here.

## 23. Supreme Court: what is held, what is missing, how stale, and what a citator can link (SC lane, 4 Nov 2026)

Evidence labels as in CLAUDE.md §9.5. Everything here is read-only against `kanoon_v1`, the source parquet and a public bucket listing. Nothing was written to a collection and nothing was paid for. No pipeline step and no verifier check was touched.

### 23.1 The 2,739 "no text" judgments have text (Measured)

The owner audit's 4,068 ids split into 2,739 served and 1,329 unserved (DECISIONS A-SC1). Of the 2,739 served: median 4,580 alphabetic words per case, minimum 160, one case under 200. All 381,271 served SC chunks have at least 5 alphabetic words. They are retrievable at rank 1 because they are ordinary records; there is nothing to filter out. Keyword half only (BM25) was run; the dense half needs a paid query embedding and was **not run**. Cited today, they pass check 2 and carry real text for check 3. The 1,329 unserved fail check 2 as `record_missing`. Guard for future loads: `scan/sc/INGEST-GUARD.md`.

### 23.2 Coverage by year (Measured; full table `scan/sc/coverage_by_year.csv`)

**Correction, 4 Nov 2026:** the first version of this section read the public bucket's per-year file counts as distinct judgments and reported 7,639 "extras". That was wrong. The bucket files each judgment under the year of its SCR volume, so about 5,200 judgments appear under two adjacent years (1962's listing holds 302 judgments whose ids say 1961). Counted by neutral id the picture is different, below.

Years are taken from the case id (`YYYY_INSC_n`). Three counts: the Open India Law source parquet; what `kanoon_v1` serves; and a public third-party bucket (`s3://indian-supreme-court-judgments`, CC BY 4.0, from `scr.sci.gov.in`), read from its 77 per-year metadata files (49 MB, the only files downloaded from it) and counted by distinct neutral id.

| Years | Source | Served | Bucket distinct ids | Bucket ids not in source |
|---|---|---|---|---|
| 1950-2005 | 20,155 | 20,151 | 20,157 | 2 |
| 2006 | 978 | 978 | 1,029 | 51 |
| 2007 | 1,321 | 1,321 | 1,321 | 0 |
| 2008 | 1,126 | 1,126 | 1,507 | 381 |
| **2009** | **1,322** | **13** | **1,322** | 0 |
| 2010-2024 | 11,674 | 11,659 | 11,675 | 1 |
| 2025 | 438 | 440 | 893 | 455 |
| 2026 | 0 | 0 | 235 | 235 |
| Total | 37,014 | 35,688 | 38,139 | 1,125 |

- **Source minus served is 1,326 net (1,329 unserved, 3 served ids not in the source). 2009 is 1,309 of the 1,329.** Every other year is at most 9 (2013). All 1,329 have no English text in the source (Hindi, Punjabi and other scripts only).
- **Against the bucket, the source holds every id the bucket lists except 1,125** (2025: 455, 2008: 381, 2026: 235, 2006: 51, and three singles in 1998, 2004 and 2022), **plus 138 distinct SCR-cited judgments the bucket lists with no neutral id** (162 rows; mostly filed under 1958-59, 1997 and 2024). The source is not short in 1950-2005 or 2007; the bucket holds every one of its 37,014 ids. Of the 1,125, none matches a source citation under another id.
- **The earlier "7,639 extras" are:** 5,277 rows that repeat an id already counted in another year's listing, 162 rows without an id, and the 1,125 ids above (43,578 rows in all).
- **What the bucket is.** It lists the court's Digital SCR (`scr.sci.gov.in`), the *reported* judgments, each with an SCR citation and a neutral citation. It is therefore **not the court's full judgment index**. Neutral ids are issued to more judgments than are reported (the source numbers run to 4,354 in 2024 against 743 held and 782 in the bucket), which is **consistent with** "reported vs all"; I have not verified it. Do not use id gaps as a completeness test.
- **The gap against the court's own full index is still not measured** (CAPTCHA, not attempted). Against the reported-judgment list the bucket gives, the served collection lacks 1,309 (2009, text) + 1,125 + 138 = about 2,570 judgments, plus every 2026 judgment.
- **Marketing consequence:** "complete Supreme Court coverage" is not supported. Defensible today: 35,688 judgments served, 1950 to 6 Nov 2025, with the 2009 English texts and about 1,260 later reported judgments missing.

### 23.3 Staleness (Measured)

The snapshot is labelled v2026.08. Latest judgment date per court in the source parquet (a few rows carry impossible future dates, up to 2088; the table takes the latest date that is not after 4 Nov 2026):

| Latest date | Courts |
|---|---|
| 2024 | Madhya Pradesh 14 Dec; Kerala 20 Dec; Punjab and Haryana 31 Dec |
| Sep-Oct 2025 | Meghalaya 15 Sep; Tripura 7 Oct; Sikkim 13 Oct; Gujarat 16 Oct; Manipur, Rajasthan, Telangana, Uttarakhand 17 Oct; Jammu and Kashmir 18 Oct |
| Nov 2025 | Madras 3; **Supreme Court 6**; Chhattisgarh 7; Bombay 14; Orissa 15; Calcutta 27 |
| Dec 2025 | Himachal Pradesh 8; Jharkhand 15; Karnataka 21; Allahabad 17 |
| 2026 (sparse) | Delhi 28 Jan; Patna 19 May; Andhra Pradesh 1 Jun; Gauhati 22 Jul |

Taking the latest month with 50 or more cases, nearly every court ends in **October 2025** (Karnataka July, Meghalaya and Tripura September); Madhya Pradesh in Feb 2024, Kerala Aug 2024, Punjab and Haryana Dec 2024. The 2026 dates are single-digit stragglers. The Supreme Court's latest is 6 Nov 2025, 363 days before 4 Nov 2026. **"August 2026" overstates the data; the supportable line is "judgments to about October-November 2025", with Madhya Pradesh, Kerala and Punjab and Haryana earlier.** This is the source's content, not the served High Court collection; served High Court dates were not checked (tunnel to 6333 not queried).

**OPEN OWNER ITEM (not resolved by the SC lane; relates to A146).** The coverage sentence ends "or anything after the data-as-of date". The latest Supreme Court judgment held is 6 Nov 2025 while the snapshot is labelled v2026.08, so the data-as-of line overstates currency by about nine months (the label reads August 2026; the data ends November 2025). The owner decides what the data-as-of line says. Measured; no wording changed.

### 23.4 Citator Phase 1: what references in SC judgment text can be linked (Measured; `scan/sc/measure_refs.py`)

35,688 cases, 1.25 billion characters, 351,980 printed references. The stored `citation` field holds one format only (SCR, 100% filled, unique), so only SCR and neutral references can be matched directly.

| Reporter | References | Share | Direct resolve |
|---|---|---|---|
| SCC | 161,706 | 45.9% | none (field holds no SCC) |
| SCR | 124,715 | 35.4% | 90.7% of 113,497 real citations (80.2% exact; 10.6% by the rule below) |
| AIR | 49,117 | 14.0% | none (39,511 are AIR SC, 9,555 other courts) |
| Other reporters | 10,200 | 2.9% | none |
| SCC OnLine | 4,236 | 1.2% | none |
| Neutral (`2018 INSC 329`) | 2,006 | 0.6% | 87.8% of 900 (1,106 are a case citing itself) |

- **SCC is the largest reporter and cannot be matched to a stored record.** Net of 11,105 running-header and self-citation artifacts, **30.5% of citations (103,762 of 339,656) link directly**; 69.5% cannot. By era the SCR share falls: before 1990, 80.8% SCR; 1990-2009, 21.6%; 2010 onwards, 34.7%, with SCC 50.0% and AIR 10.9%.
- **A concordance built from the text itself adds at most 9.1%** (31,035 references): where an SCC or AIR is printed within 90 characters of a resolved SCR, the pair is recorded. 58.6% of standalone SCC references (63,732 of 108,785) hit a key with conflicting partners, so the concordance is unreliable and is kept separate. A usable SCC link needs an outside SCC-to-SCR table; none is held. Not built.
- **SCR unresolved (10,525, 9.3%):** volume not held 3,727; pinpoint page cited as a first page 4,844; page past the last held case 782; ambiguous without volume 523; year off by one 274; page not a start 288; year outside 1950-2025 84. Many are OCR damage (`[19621 2 s.c.R. 5183`). Rule used: a citation without volume (`[1950] S.C.R. 88`) resolves only when exactly one stored case has that year and first page (11,992 references). That is a heuristic; a wrong link is possible and is **not verified**.
- **Running page headers read as citations:** 10,219 in the judgment's own volume plus 719 beside "SUPREME COURT REPORTS". They are removed before counting.
- **Case name only:** of 348,537 case-name mentions ("A v. B"), 216,886 (62.2%) have a citation next to them, 34,270 (9.8%) a citation of another year, 94,845 (27.2%) none. The 27.2% is an upper bound (a cite two sentences away is missed) and is counted as lost, not resolved.
- One text (2021_INSC_284, 829,000 characters) made the first SCR pattern backtrack for hours; the pattern now allows at most 4 tokens between year and S.C.R., tested in `tests/citator/test_refs.py`.

### 23.5 `treatment_mentions` (Measured; provenance partly open)

Present on 8.7% of SC points (32,991). The source parquet has **no such column**, nor does any of the 75 Open India Law parquets, and the dataset README does not mention it, so it was added when the Qdrant collection was built, by someone not identified here (**Needs verification: ask Vaquill**). From a sample of 6,000 tagged and 6,000 untagged SC chunks: it is **per chunk, a keyword flag on the chunk's own words**, with a tag list such as AFFIRMED, APPLIED, DISTINGUISHED, FOLLOWED, DISSENTED, SET_ASIDE, OVERRULED. DISTINGUISHED, FOLLOWED, DISSENTED, SET_ASIDE and REVERSED chunks contain the stem 100% of the time; untagged chunks contain it 0 to 45% of the time (FOLLOWED 37%, APPLIED 45%, the common words). OVERRULED chunks contain "overrul" in 85%. It names **no target case**, so it cannot say which case was overruled; it flags a sentence somewhere in the chunk. Reading 8 OVERRULED chunks: 7 state that an earlier decision "stands overruled" or "was overruled" (one is a general principle, not a holding). It is derived from text we also hold, so nothing here is hidden; but it is a lexical hint, not a determination, and a missing tag proves nothing (91.3% of chunks carry none). **Not used in any output. Trust: usable only as a pointer that says "read this chunk", never as a status.**

### 23.6 OCR noise against verifier check 3 (Measured exposure; verifier untouched)

`core/verify.py normalise` (line 236) turns punctuation into spaces and collapses whitespace but keeps every letter, so OCR damage inside a quoted stretch makes an honest quote fail "quoted words appear exactly". `scan/sc/ocr_noise.py` cut 12,000 sampled chunks (3,000 per era, 585,000 twelve-word windows) and counted windows that contain an artifact a person quoting the printed text would not reproduce.

| Years | Windows with at least one artifact | Main cause |
|---|---|---|
| 1950-1969 | 3.5% | margin letters 1.4%, page headers 1.1% |
| 1970-1989 | 4.0% | margin letters 2.6% |
| 1990-2009 | 9.4% | margin letters 7.8% |
| 2010-2025 | 8.8% | glued words 4.0%, margin letters 3.9% |

Margin letters are the printed column marks A to H sitting inside sentences ("held her C guilty of contempt", "name of the H accused"): a quote without the letter fails. Glued words in recent years ("theRegistry", "anDindependent"). This is an **exposure, an upper bound** on quotes that could fail for OCR reasons: it assumes the quoter types the clean printed words and the quote spans 12 words; shorter quotes meet less. The real failure rate needs a quote set from a clean copy; **not measured**. Lane B's separate finding stands: check 3 does nothing on paraphrase. Not touched.

**OPEN OWNER ITEM.** Should check 3's comparison normalise OCR artefacts (margin letters A-H between words, glued words, `l` for `1`)? Today `normalise` (`core/verify.py:236`) tidies spaces and punctuation but keeps every letter, so up to 3.5% to 9.4% of 12-word stretches (by era; margin letters 1.4% to 7.8%) can fail an honest quote. Lane B separately measured (relayed to me by the owner; not re-measured here) that check 3 does nothing at all on paraphrased sentences, so the two problems pull opposite ways: the check is too strict on faithful quotes of OCR-damaged text and silent on paraphrase. The owner decides; the SC lane has not changed the verifier.

### 23.7 Official listing check for the court's index (Checked)

No RSS feed or API for judgments was found on sci.gov.in; the court's listing sits behind a CAPTCHA. The Supreme Court publishes an annual report whose tables were not opened. The public bucket above names `scr.sci.gov.in` as its source and asks users to avoid high-concurrency scraping. Per-year metadata (`metadata/parquet/year=YYYY/metadata.parquet`) would give id-level lists for (a) judgments on that index we hold nowhere and (b) held judgments not on it; **not downloaded** pending approval.

### 23.8 Pricing the gap from the bucket (Estimate from Measured parts; nothing ingested)

Method: the bucket's PDF file names carry volume and page range (`2009_10_1006_1012_EN.pdf` is 7 SCR pages), so page counts come from the listing. I downloaded **8 sample PDFs of 2009 (3.5 MB total, chosen across the size range)** to measure text per page: all 8 have a text layer (extracted with `pdftotext`, no OCR), 95 pages, 216,625 characters, **2,280 characters per page** (range 1,973 to 2,385). A served SC chunk averages 3,275 new characters and 908 billed tokens (3,000 sampled chunks, tokenizer count). Rate: voyage-4 $0.06 per million tokens, Batch 33% off, so $0.0402 (vendor pricing fetched 4 Nov, via `data/voyage_token_count.py`); INR at the repo's assumed Rs 85 per USD. Free-token allowance not assumed.

| Job | PDFs / records | Size | SCR pages | Characters | Chunks | Tokens | voyage-4 batch |
|---|---|---|---|---|---|---|---|
| 2009 English | 1,326 | 652.6 MiB | 19,157 | 43.7 M | about 13,300 | about 12.1 M | $0.49 (Rs 41) |
| Bucket-only reported judgments (1,125 ids, 138 no-id) | 1,263 | not listed | 24,335 (1,225 with a page range) | 55.5 M | about 16,900 | about 15.4 M | $0.62 (Rs 53) |
| Both | about 2,590 | | about 43,500 | 99 M | about 30,300 | about 27.5 M | **$1.11 (Rs 94)** |

Range plus or minus 20% (the sample PDFs yield 10% fewer tokens per character than served text, so this leans high). **Embedding is not the cost; reading is.** Open: PDFs carry the printed margin letters and page headers (DATA-GAPS 23.6), so the same noise enters unless cleaned; chunking and sparse vectors must match the served collection; and text read from PDFs has not been compared with the source's text for the same case. **Not ingested, not embedded, no spend. Waiting for owner approval (cost gate).**

### 23.9 Is the bucket a refresh source? (Checked)

- **Maintained:** the 2026 listing (235 distinct judgments, decisions to **6 Oct 2026**, scraped 17 Oct 2026) was last modified 18 Oct 2026; all other years' metadata 11 Apr 2026; 2009 PDFs 4 Jun 2026; 2009 archive 15 Jan 2026. So updates occur, at intervals of two to five months in what I saw; the registry says "Bi-monthly" and I did not confirm that. Run by Dattam Labs (a private company, contact on the registry page). Judgments after 6 Nov 2025 exist only there among our candidate sources.
- **Terms:** CC BY 4.0 on the dataset. The registry page states no conditions from the court or eCourts; its README asks users to avoid high-concurrency scraping and to prefer the tar and parquet files. The court's own terms for reuse of judgments were **not found** (`digiscr.sci.gov.in` is decommissioned; the portal moved to `scr.sci.gov.in`).
- **Fit:** it carries a neutral id, SCR citation, decision date, disposal nature, judge and a PDF with a text layer per judgment: enough to key to our ids. Cover-only: reported judgments, English plus regional PDFs. Risks: a third party, not the court; no change log; PDF text, not the source's text. **A candidate ingestion source for refresh; not a decision.** Nothing was ingested.

### 23.10 Case-level citation coverage (Measured; `scan/sc/measure_refs.py`, `inbound`)

A cited case needs only one reference in SCR or neutral form to be linked. Counting distinct citing judgments per cited judgment (self-citations and running headers removed), over the 35,688 served cases:

- **17,418 (48.8%) have at least one resolvable inbound citation; 18,270 (51.2%) have none.** Total links: 72,101 (citing judgment, cited judgment) pairs.
- Inbound count per case: median 0, mean 2.0, 75th percentile 2, 90th 5, 99th 22, maximum 174 (`1978_INSC_16`; then 136, 125, 106, 105). Cases with exactly 0: 18,270; 1: 6,426; 2: 3,339; 3-5: 4,297; 6-10: 2,004; 11-50: 1,291; 51-200: 61; none above 200. The top 1% of cases hold 18.8% of links.
- **By the cited case's decade it is lopsided:** 1950-69: 73.0% have an inbound link; 1970-89: 57.4%; 1990-2009: 46.4%; 2010-19: 48.4%; **2020-25: 23.0%**. The cases a recent court is most likely to overrule are old; they are the best covered. But a *recent* judgment that overrules is the citing side, and recent judgments cite mostly in SCC form (50.0% SCC, 34.7% SCR), so its reference to the older case resolves only if the SCR form is also printed.
- **Reading it:** a case with 0 resolved inbound links is **not** a case with no citing judgment; it means none was written in SCR form. The count is a floor. Nothing in a citator built on it may read "not cited" or "no adverse treatment found" as clearance.

### 23.11 Is there an SCC-to-SCR concordance outside our data? (Checked; nothing accessed)

- **Official table:** the Supreme Court's Judges Library publishes an Equivalent Citation Table (four PDF volumes at `main.sci.gov.in/pdf/ECT/journal1.pdf` to `journal4.pdf`, 1950 to date, each volume ordered by a different reporter: AIR, SCR, SCC, JT, SCALE), per a third-party article of 15 May 2022. **I could not open it:** `main.sci.gov.in` does not resolve from here and `www.sci.gov.in` returns 403 to an automated request, so I stopped (not scraped). Licence/reuse terms **not found**; format is PDF, not machine-readable, and whether it is current or complete is **not verified**.
- **Bucket:** carries SCR and neutral citation only, no SCC.
- **Other:** third-party web tables (no licence stated); a journal-publisher table (SCC Online) is commercial. No open, licensed, machine-readable SCC-to-SCR dataset was found.
- **Owner action:** to use the official table someone must fetch the four PDFs by hand and confirm the court's reuse terms. Until then SCC cannot be linked authoritatively.
- **Does the printed report carry its own SCC or AIR equivalent? No, not in what I could read (Measured, 5 Nov 2026).** The bucket's metadata cannot give one: `citation` is the SCR string and `case_id` the neutral citation, with no equivalent-citation field. Eight 2009 PDFs from the bucket (read in full, no new download): page 1 holds the SCR running head (`[2009] 6 S.C.R. 160`), the party names, case number, date, bench, the headnote, and the margin letters; the last page ends with the reporter's initials and the disposition ("Appeal allowed."). **0 of 8 print an equivalent citation for the judgment itself.** SCC or AIR strings do appear in 6 of the 8, but each refers to *another* case: inside the headnote ("Secretary, State of Karnataka vs. Umadevi (3): 2006 (4) SCC 1, followed"), in a printed "Case Law Reference" table on page 1 ("2006 (4) SCC 1  Followed.  Para 3"), and in the body. Whole served corpus, same question: the first 700 characters of each case's first chunk hold an SCC, AIR, JT or SCALE citation in only 37 of 35,688 cases (0.1%), all headnote references to other cases, none a labelled own-equivalent. So there is **no consistent position to extract an own SCC or AIR equivalent from the report text**, and the SCC-to-SCR mapping cannot be built from this source. Limits: 8 PDFs from one year; the header window is 700 characters; later or earlier print styles (the Judges Library table's column) are not seen in these. The remaining routes are the Equivalent Citation Table above (official, not opened) or a request to the Court's Registry, the owner's to pursue.
- **Side observation, not built:** the printed "Case Law Reference" table and headnote pair a cited case's name with its SCC citation and an editor's word ("Followed", "Relied on"). That is name-plus-citation, in the Court's own report, and could seed a name-to-SCC list. It is not own-equivalent data, resolving it back to a record would rest on case names (counted as lost by the Phase 1 rule), and the treatment words are Phase 2 (needs an advocate).

### 23.12 Bucket PDF text against our stored text, same cases (Measured, 10 cases; the spend is NOT done)

Ten cases we already hold, one from each stretch of years (1959, 1968, 1978, 1988, 1997, 2004, 2007, 2013, 2019, 2024), their English PDFs fetched from the bucket one at a time (about 5 MB), text extracted with `pdftotext -layout`, compared with our stored chunks rebuilt without overlap and with the layout markers removed (`scan/sc/pdf_vs_stored.py`). Mean per 1,000 words, stored against PDF:

| Artifact | Stored | PDF |
|---|---|---|
| Margin letters A-H between words | 3.77 | 2.21 |
| Glued words ("twopersons") | 0.79 | 0.20 |
| `l`/`I` for `1` in numbers | 0.10 | 0.10 |
| Brackets swapped | 0.28 | 0.39 |
| **Running page headers kept in the text** | 0.71 | **1.23** |
| **Line-break hyphens left ("deter- mination")** | 0.07 | **3.60** (older cases 6 to 10) |
| Words not in a dictionary (%) | 18.78 | 18.42 |

Word-for-word the texts agree 97.1% to 99.0% in nine cases and 88.1% in the tenth (`2019_INSC_557`, where our stored text has glued words and the PDF does not). **They are the same OCR underneath; the bucket's extraction is not materially worse.** It is cleaner on glued words and margin letters, and carries two problems the stored text had already removed: unjoined line-break hyphens and more page headers. Both are mechanical to clean (join hyphen-newline; drop lines that match the running head). The lower margin-letter count has a caveat: with `-layout` the letters sit in a margin column, so my detector (which needs a letter between two lower-case words) may miss some; I have not hand-counted them.

**Against verifier check 3 and A147:** the same exposure, not worse. Margin letters are not removed by extraction; but a PDF read with layout keeps them in an outer column, so removing them by position is possible where the stored text lost that information. Not built. No verifier change.

Bucket completeness for the target set: all 1,322 ids of 2009 and all 1,125 bucket-only ids have an English PDF (371 MB for the 1,125; 137 of the 138 no-id records do, 100 MB). 

**Not done: the embedding.** (1) There is no `VOYAGE_API_KEY` in this checkout (`.env` is absent and the variable is unset); I did not look elsewhere. (2) The existing path, `VoyageClient` on the standard endpoint, bills list price, so the same tokens cost about $1.65 (Rs 140) at voyage-4, not the $1.11 batch estimate: 49% over, outside the plus or minus 20%. No Batch API client exists in the repo. (3) The stored SC vectors are voyage-4-large (it reproduces them at 0.9987 to 0.9995, with some below 0.999) and voyage-4 gives 0.94 to 0.96 on them, so a 0.999 reproduction gate has to run on chunks stored with voyage-4 (the High Court control reproduces at 0.999984). Nothing was spent.

### 23.13 Does the "Case Law Reference" table survive in the text we hold? Mostly not; the headnote's parallel citations do (Measured; `scan/sc/measure_case_law_table.py`; nothing built)

The Court's reporter prints, after the headnote, a table with one row per cited case: `2011 (5) SCR 729   referred to   Para 1`. Searched the first 15,000 characters of all 35,688 served cases (whole-text search finds the heading in 7,155, 20.0%):

- **The heading survives in 6,103 cases (17.1%), almost all from 2010**: 2010s 4,475 of 7,788 (57.5%); 2020s 1,367 of 4,311 (31.7%); 2000s 210; before 2000, 51. Reports before about 2005 do not print it.
- **The rows survive in few of them.** Rows parse (citation, editor's word, `Para N`) in **1,503 cases (4.2% of all)**, 2,818 rows. Of the 6,103 headings, **3,120 (51%) have no row-like text at all after them**. I opened three of those in the bucket's PDFs (2018_INSC_517, 2014_INSC_738, 2018_INSC_1032): **all three print a full table (4 to 7 rows), none of which is in our stored text.** So the layout parser kept the heading and dropped the table body, in at least these cases. A further 1,521 headings have some row text my strict parser misses (reporters like E.L.T., a word glued to "Para"); those are a parser limit, not a loss. A table that runs onto page 2 keeps only its first page of rows (2013_INSC_224: 3 of 12 rows). Chunking is not the cause: of 1,503 cases with parsed rows, 1,460 sit whole in the heading's chunk and 2 are split.
- **Rows parsed (2,818):** SCR 2,423; AIR 174; SCC 111; other reporters 109; SCC OnLine 1. SCR rows resolve to a served record in 2,207 of 2,423 (91.1%): 2,097 exact, 110 by the volume-omitted rule. Overall 78.3% of parsed rows. Editor's words (text only, not interpreted): referred to 1,304; relied on 1,120; distinguished 149; held inapplicable 108; cited 57; followed 48; approved 9; held applicable 7; **overruled 7**; affirmed 4; others 4. 86% are the two neutral words.
- **Verdict:** the table is in the PDFs, not in what we hold, for about half of the cases that print it. Getting it is an extraction job on the bucket's PDFs for the roughly 6,100 cases with the heading (Estimate: about 3 GB at 0.52 MB per PDF), plus parsing; no embedding. It is the owner's call. The treatment words are Phase 2 and are not read here.

**What does survive, and is better for the SCC question:** the headnote's list of authorities, printed above the table, gives each cited case with **both** citations joined by a colon, for example `Brij Mohan Lal v. Union of India (2002) 5 SCC 1 : [2002] 3 SCR 810 ... – relied on.` Counting two citations joined by `:` or `=` with one of them SCR:

- **7,796 cases (21.8%) carry such pairs, 34,198 pairs**: 2010s 4,292 (55.1%); **2020s 3,321 (77.0%)**; before 2010, about 180 in all. By kind: SCC 28,541; AIR 4,023; neutral 1,302; SCC OnLine 256.
- **SCC to SCR from the Court's own report:** of 28,184 distinct SCC citations in the served text, **11,328 (40.2%) appear in at least one pair; 10,127 (35.9%) map to one SCR record we hold; 130 conflict; 870 pair with an SCR not held.** AIR: of 13,804, 2,572 (18.6%) paired, 1,545 (11.2%) to one held record. This is far cleaner than the 90-character adjacency in 23.4 (58.6% conflicting), because the colon makes the pairing positional.
- **Spot checks (2):** Maneka Gandhi `(1978) 1 SCC 248` pairs with `[1978] 2 SCR 621` in 23+ places (correct). Kesavananda `(1973) 4 SCC 225` appears once, paired with `[1973] 2 SCR 1089`, which is not the Judges Library entry I saw cited elsewhere (`[1973] Suppl. SCR 1`): **a pair seen once may be wrong; use only repeated or cross-checked pairs.**
- **Not measured:** the share of SCC *mentions* (rather than distinct citations) that the pairs would cover; whether a pair's SCR side is the same judgment as its name; the 2020s coverage in the original PDFs. Nothing was built.

### 23.14 The headnote SCC-to-SCR map: how many pairs repeat, whether it is right, and what it does to coverage (Measured; `scan/sc/pair_map.py`; nothing built)

**Correction to 23.13.** The Kesavananda "contradiction" was the outlier. With every printing counted: `(1973) 4 SCC 225` is paired with `1973_INSC_91` by 3 cases and with `1972_INSC_292` by 1; the first is the right one.

**1. Repetition.** Pairs whose SCR side is a held record, with the case's own pair removed, counting distinct printing cases. SCC: 10,458 keys; 10,328 point to one target and 130 to two or more. Of the 10,328: **4,965 are printed by 2 or more independent cases, 2,837 by 3 or more, 1,173 by 5 or more.** Of the 130 conflicting keys, 98 have a clear winner (at least 2 cases and twice the runner-up). AIR (Supreme Court only): 1,737 single-target keys; 325 in 2 or more cases; 91 in 3 or more.

**2. Ground truth: the Judges Library table of 64 landmark cases** (`2024061128.pdf`, 42,745 bytes, fetched once; the one file downloaded). Four rows cannot be tested (row 19 gives no SCR; row 54 gives SCC OnLine only; rows 59 and 64 give SCALE only); five rows wrap across lines and I transcribed their SCC cell by hand from the printed text (6, 7, 18, 24, 49; row 49 prints `SCC-396`, read as 396). Of the 60 testable, the SCR record is held for 57.

| Rule applied to the map | Right | Wrong | Not covered |
|---|---|---|---|
| Winner is the only target, or at least twice the runner-up (any count) | 54 | **0** | 6 |
| Winner printed by 2 or more cases and twice the runner-up | 47 | **0** | 13 |
| Winner printed by 3 or more cases and twice the runner-up | 39 | **0** | 21 |

By raw entry: 48 keys single-target and right; 6 keys carry a wrong second target, **every one of the six wrong targets printed exactly once** (the right target printed 3, 91, 27, 32, 2 and 6 times; the sixth, Kesavananda, 3); 6 absent. So **the repetition (or majority) rule is supported by this evidence: it removed every wrong pair.** What the table cannot show is whether a *lone* single-occurrence pair with no rival is safe: 7 such keys are in the table and all 7 are right, a sample too small to rely on (zero wrong in 7 allows a true error rate up to about 35%). The usable map is therefore the "2 or more cases and twice the runner-up" set, about 5,060 SCC keys (4,965 + 98), unless the owner accepts lone pairs. This tests whether a *key* maps to the right case, on clean landmark keys; it does not test OCR-damaged keys in running text. A proxy: of 3,937 resolved standalone SCC mentions in a 2,500-case sample, **81.1% have a distinctive word of the target's title within 200 characters before** (the rest are mostly footnote lists with no name; the ones I read were right). A lower bound on correctness, not an estimate of it.

**3. Coverage with the map applied (35,688 cases).**

| Map rule | Cases with at least one inbound link | Links (citing case, cited case) | Mean per case | Mentions resolved |
|---|---|---|---|---|
| none (23.10) | 17,418 (48.8%) | 72,101 | 2.02 | 103,762 of 339,656 (30.5%) |
| 3 or more cases | 17,418 (48.8%) | 87,335 (+21%) | 2.45 | about 144,400 (42.5%) |
| **2 or more cases** | **17,418 (48.8%)** | **92,607 (+28%)** | 2.59 | about 157,300 (46.3%) |
| any (majority) | 17,419 (48.8%) | 100,354 (+39%) | 2.81 | about 174,700 (51.4%) |

**The case-level figure does not move: 48.8% to 48.8%, by construction, under every rule.** A pair is only in the map because some case printed that case's SCR citation next to its SCC citation, so every case in the map already has an inbound link, from the case that printed the pair. The map can only add links to cases already linked; it cannot reach a case that has been cited only in SCC form with no pair printed anywhere. By era the case-level coverage is unchanged (1950-69 73.0%, 1970-89 57.4%, 1990-2009 46.4%, 2010-19 48.4%, **2020-25 23.0%**). What the map does raise is **link density**, and the mentions that resolve: 46.3% instead of 30.5% at the "2 or more" rule (standalone SCC mentions 50,478 and AIR 3,043 newly linked). For a citator the link count per case is the better measure of whether a later overruling could be found, and the per-case recall of true inbound citations is **not measured** (the true inbound set is unknown).

**Owner item (parked, open): extract the "Case Law Reference" table from the bucket's PDFs.** About 6,100 PDFs (the cases whose stored text carries the heading), about 3.2 GB (Estimate, at 0.52 MB per PDF), no embedding cost, one PDF at a time per the registry's request; plus a parser for the table (the PDFs print it cleanly, e.g. 2018_INSC_517 has six rows). It would add the editor's word per cited case (Phase 2 material) and rows the headnote omits. Parked in favour of the headnote route, which is free and already in our text; reopen if the headnote route under-delivers.

### 23.15 Citator Phase 1 BUILT: the links, the map, and what density did and did not do (Measured 5 Nov 2026; `scan/sc/build_links.py`, `core/citator/links.py`, `core/citator/pairmap.py`; output in `data/citator/`)

> **READ THIS FIRST. Case-level coverage does not move, by construction, and the other 51% is structural.** 17,418 of 35,688 served judgments (48.8%) have at least one inbound link before the map and **the same 17,418 after it; 0 cases gained a first link.** The map is derived from headnote pairs printed by judgments that were already linked, so every case it can reach already has an inbound link from the judgment that printed the pair. It cannot reach a case cited only in SCC form with no pair printed anywhere. The 18,270 cases with no inbound link (51.2%) need an **external SCC-to-SCR concordance**: the Supreme Court's Judges Library Equivalent Citation Table (four PDF volumes, section 23.11) or ILR. **Both are the owner's to pursue** (fetch, confirm reuse terms, or a request to the Registry). No amount of extra work on our own text closes this. Expect the question to be asked again; this paragraph is the answer.

**What was built.** The rule from 23.14, unchanged: an SCC citation, or an AIR Supreme Court citation, is mapped to a record only when the winning record is printed by **at least 2 distinct judgments and by at least twice as many as any other record that citation was paired with**. Evidence is a set of citing judgments, so one judgment printing a pair ten times counts once; a judgment's own pair is removed. Trusted keys: 5,391 (5,063 SCC, 328 AIR). Links: 72,101 direct (SCR or neutral citation equals a stored record) plus 20,506 mapped-only, kept apart by a `via` field = 92,607 (citing, cited) pairs. Direct reproduces 23.10 exactly (72,101); the total reproduces the 23.14 "2 or more" row exactly (92,607). **Validation, re-run on the built map against the Judges Library table of 64 landmark cases: 47 right, 0 wrong, 10 not covered** (plus 7 rows that cannot be tested: no SCR given, or the SCR record is not held); a lone pair is not trusted. Ground truth is `scan/sc/judges_library_landmark.json` (a first transcription merged rows 17/18 and 23/24 and omitted the five hand-transcribed wrapped rows; the file holds the corrected keys, and the one apparent "wrong" that surfaced in this run was that transcription error, not the map).

**Link density per case, before (direct only) and after (with the map). This is the number that decides whether an overruling gets spotted.**

| Inbound links per case | Before | After |
|---|---|---|
| 0 | 18,270 | 18,270 |
| 1 | 6,426 | 6,418 |
| 2 | 3,339 | 2,869 |
| 3-5 | 4,297 | 3,684 |
| 6-10 | 2,004 | 2,255 |
| 11-50 | 1,291 | 2,068 |
| 51-200 | 61 | 121 |
| 201+ | 0 | 3 |
| mean / median | 2.02 / 0 | 2.595 / 0 |
| 75th / 90th / 99th percentile | 2 / 5 / 22 | 2 / 7 / 31 |
| maximum | 174 | 258 |
| cases with 2 or more | 10,992 | 11,000 |
| cases with 3 or more | 7,653 | 8,131 |
| share of all links held by the top 1% of cases | 18.8% | 20.3% |

**Reading it.** 3,907 cases gained links, but only **8 moved from fewer than 2 links to 2 or more**, and the single-link bucket barely moved (6,426 to 6,418). The extra links went to cases that were already well linked: the top 1% now hold 20.3% of links against 18.8%. So the map makes the heavily cited landmark cases better covered and does almost nothing for the thinly linked ones, which are the ones where a single missed citing judgment is most likely to hide an overruling. By decade of the cited case, mean inbound links rise most for the 1970s (2.86 to 3.63), 1980s (2.51 to 3.79) and 1990s (1.34 to 2.23) and least for the 2020s (0.42 to 0.49); the share of 2020s cases with two or more links stays 7.6% (full table in `data/citator/sc_link_density.json`). Per-case recall of true inbound citations is still **not measured** (the true inbound set is unknown).

**Design rule, enforced in code.** Nothing renders as "still good law". A zero means no judgment in our data cites the case in a form we can read, never clearance. `core/citator/links.py` has no `status`, `treatment` or `good_law` attribute; every sentence the model can produce is one of two fixed templates (`ZERO_READABLE`, `SOME_READABLE`), both of which say the count is a minimum and say nothing of how a citing judgment treated the case. `tests/citator/test_links.py` fails if such an attribute appears, if any sentence the model can return matches clearance wording ("good law", "no adverse", "not cited", "clear", "safe", "valid", and others), or if code in `core`, `api` or `web/src` asserts good-law standing. Treatment (followed, distinguished, overruled) is Phase 2 and needs an advocate; the "Case Law Reference" extraction stays parked (end of 23.14).

**Not wired.** Nothing serves these links yet: no API route, no screen, no pipeline step, no verifier check changed. Rebuild: `python scan/sc/build_links.py SC_TEXT2.db OUT_DIR --validate scan/sc/judges_library_landmark.json` (about a minute; the sqlite dump is made by `scan/sc/dump_text.py`); output is byte-stable.

## 24. The 10 remaining `not_found`: 5 absent text, 3 present but lost to a source label, 2 filter problems (5 Nov 2026; CORRECTED the same day)

**Correction first.** The first version of this section (commit `c42b4a3`) said 8 of the 10 were data holes and called the three verifier removals "the verifier working as designed". **That was wrong for three of them.** For IPC 34 (q010), NDPS 37 (q036) and Registration Act 49 (q075) the section's text IS in the data, appended inside the chunk of the section before it (IPC 34 inside the chunk labelled 33, NDPS 37 inside 36C, Registration Act 49 inside 48), and the gate was right to keep that chunk. The first version judged by the chunk's label and by the opening words of its text, which are the previous section's.

**What was measured.** After the search fix (DECISIONS A144) 10 of the 100 stub questions still come back `not_found`. Each was run twice through the real pipeline (`evals/labelling/diagnose_not_found.py`; per-passage ratings and scores in `~/qdrant-kanoon/labelling/not_found_diagnosis.json`), with the same outcome both times. Nothing was emptied at step 5; the gate emptied 7 and verify emptied 3. The 0.6 threshold and the 50 / 10 / 8 counts were not touched.

| Cause | Questions | What happened |
|---|---|---|
| **The text is absent from the Act** | q031, q032, q070 (CPC sections 9 and 11); q037, q069 (Limitation Act section 5) | No chunk of the Act holds the text. A phrase search of all 1,554 CPC points for the words of Section 9 and of Section 11, and of all 72 Limitation Act points for "sufficient cause", finds nothing. The chunks labelled `Section 9:` and `Section 11:` in the CPC are Order rules (for example `Section 9: Decree for recovery of immovable property`). The gate rated every retrieved passage not relevant, correctly. |
| **The text is present, inside the neighbouring section's chunk; the answer was lost to the writer's source label** | q010 (IPC 34), q036 (NDPS 37), q075 (Registration Act 49) | The gate kept the chunk holding the text (rated `answers`, correctly). The writer then cited a label that does not exist: `[S2]` and `[S8]` or `[S9]` when the gate kept only one passage, S1. Check 1 of the verifier removes a citation whose label is not among the kept passages (`not_retrieved`), so correct text was removed and the question came back `not_found`. The answer prompt (`core/prompts/answer.txt`) says "for example [S2]", which the model copies when one passage was kept. In the 100-question run this removed the only citation in 2 questions (q010, q075); the diagnosis run showed it for q036 too. |
| **A filter excluded the right chunks** | q072, q050 | q072 (temporary injunction): the decision step invented `section: 39` for a question that names no section (it means Order XXXIX, which the prompt tells it to leave null); the filter kept 3 unrelated Order 21 chunks and excluded the provision that is in the data (`IND_central_2191_s001_d42`, the Order XXXIX rule 1 text). q050 (anticipatory bail under section 138 NI Act): the section is present (2 chunks) but a named-section search returns only the statute, never the judgments the question needs. |

**What this changes about the data.** A section number is not a reliable address: the chunker appends an amended or substituted section to the one before it, so some sections can be found only inside a neighbour. DATA-GAPS section 26 measures how often, across all 1,568 Central Acts.

**The gate, rechecked.** Of the 49 questions that name a section, 36 kept at least one Act-section passage, and in 35 of the 36 a kept passage holds the asked section's text (by label or by its heading inside the text). The exception is q041 (HSA section 6): the kept chunks are other sections' text and the answer reproduced a sub-section fragment, rated 1.00. 13 of the 49 kept no Act-section passage (7 are CrPC lookups, where the Act is absent; 5 are the `not_found` above; q027 answered from judgments only, not examined). **The two cases first reported as the gate being "certain about a neighbouring provision" (q010 and q036) were not gate errors.**

**Check that would settle the absent text.** For each served Act, compare its sections with the section list in the India Code source (the dataset's `text_url` or the owner's earlier repo's `MISSING-SECTIONS.md`); not done here.

## 25. For a paraphrased cited sentence, check 3 does nothing and the mechanical guarantee is check 4, a model's opinion (5 Nov 2026, measured)

Section 22 found five misattributed sentences. Four of them carried no quotation marks, so check 3 had nothing to test. That is a bigger finding than the 6.3%.

### What it means

`CLAUDE.md` §5 lists four checks. For a cited sentence that paraphrases and does not quote:
1. **Retrieved for this question** passes whenever the label is one the writer was handed (S1 to S8). The writer can only cite what it was given, so this tests the label and not the claim.
2. **Record exists** passes whenever that passage's record is in the store. Same: it tests the record, not the claim.
3. **Quotes match** is **vacuous**: no quoted words, nothing to compare.
4. **Claim supported** is a model's judgement.

So for a paraphrase the whole mechanical guarantee collapses onto check 4. Section 22 measured check 4 passing five defective pairs of five. Check 3 is the only check that proves words were written by the court, and it proves it only for words in quotation marks.

### How often check 3 fires (counted with the verifier's own `_quotes`)

| Run | Pairs | Pairs with a quoted span | Answers with any quote |
|---|---|---|---|
| New answer prompt (A137), the 79 pairs of section 22 | 79 | **5 (6.3%)** | 3 of 35 drafts that carried a marker |
| Old answer prompt | 145 | 40 (27.6%) | 21 of 39 |
| The 33 questions cited under both prompts, old | 129 | 38 (29.5%) | |
| The same 33, new | 76 | 5 (6.6%) | |

In the new run **74 of 79 pairs (93.7%) gave check 3 nothing to test.** The five that did: q002 (two statutory definitions copied verbatim), q008 (two, "cruelty"), and q088 (the counsel's argument of section 22). **Correction, 5 Nov 2026:** this sentence first said all five passed check 3 and no honest quote was stripped. That was wrong, and I had not run the verifier to see. Replaying the saved drafts through the real `verify()` (check 4 forced to pass, so only checks 1 to 3 and A137 act) shows check 3 removed **2 sentences** of the 79: q008's `"Cruelty" also means harassment...` (the passage has lowercase `cruelty`; check 3 keeps case, and the sentence starts with a capital), and q100's sentence about money laundering, which has no quotation at all but a possessive curly apostrophe (`nation’s`): check 3 counts an unmatched `’` as a stray quotation mark and fails closed. Both removals are honest text lost, 2.5% of the pairs; neither was a fabrication. Section 28 has the second one as a defect class.

**A side effect of the A137 prompt change, reported plainly.** On the same 33 questions the share of pairs with a quote fell from 29.5% to 6.6%. The line that tells the writer to quote only exact words is unchanged (`diff` of the two prompts); what changed is "every sentence ends in a marker, no intro, no summary". I cannot separate cause from run-to-run variation (one run per prompt), but the direction is large. In practice the prompt that made every sentence cite also made the writer paraphrase more, so check 3 now covers less of an answer. That is not a reason to undo A137. It is a reason to know where the guarantee sits.

### What is not done

- **The verifier is unchanged**, and check 3 is not loosened. A147 (the owner, deferred) records that OCR damage affects 3.5% to 9.4% of 12-word windows and can fail an honest quote; the answer there is already "no" to making check 3 tolerant, and the fix when it comes is cleaning a copy of the record text. This section agrees with that: a weaker check 3 would trade a visible error for an invisible one, and check 3 is already firing on only 6% of pairs.
- **A prompt lever exists and is the owner's call, not applied:** ask the writer to quote statute wording verbatim when it states what a provision says. That would put check 3 on the sentences that state law. It is an answer-prompt change with its own cost (more quotes means more exposure to the OCR damage A147 describes), so it needs the same blast-radius measurement A137 had.
- **Check 4 stays unmeasured against a ground truth.** Section 22 gives the advocate review that would supply one.

### Limits

79 and 145 pairs, one run per prompt, one model, practice-fixture retrieval. The quote count is exact for these drafts; what it says about real traffic is not known.

## 26. Section-level coverage of the Central Acts (5 Nov 2026, measured; the full tables are in `docs/SECTION-COVERAGE.md`)

Section 20 counted Acts: 1,568 held. This counts sections, free and read-only, for every Central Act in `kanoon_v1` (`scan/section_coverage.py`, the owner's earlier checker's rules ported, so the two can be compared). **"Held" is true of the Acts and false of the sections.**

| | Acts | Sections expected (lower bound) | A chunk is labelled with the number | No chunk labelled | Of those, text inside the chunk before | **Likely absent** |
|---|---:|---:|---:|---:|---:|---:|
| All Central Acts | 1,568 | 59,053 | 35,371 | 23,682 | 2,590 | **21,092 (35.7%)** |
| **In force** | 848 | 38,294 | 28,710 | 9,584 (25.0%) | 1,733 | **7,851 (20.5%)** |
| Repealed | 710 | 20,547 | 6,497 | 14,050 | 854 | 13,196 (64.2%) |

* **In force: 734 of 848 Acts lack a chunk for at least one section number; only 114 have every number from 1 to N.** 154 hold fewer than half of the sections they should. **The sections with no text anywhere are between 7,851 and 9,584 of 38,294 (20.5% to 25.0%)**, a range because the "text inside the chunk before" credit slightly over-states what is present (hand-checked: 13 of 16 random credits were the real section).
* **Structure.** Of the 848 Acts in force, 787 are stored section by section, 45 are stubs (1 to 3 labelled sections in an Act that should have 10 or more: for example the National Bank for Agriculture and Rural Development Act 1/60, the Deposit Insurance and Credit Guarantee Corporation Act 1/50, the Customs Act 2/58, the National Security Act 1/21) and 16 are stored as unlabelled text blocks (the Protection of Human Rights Act, the Arms Act among them), which a lookup by section number cannot find.
* **Foundational sections absent.** 77 Acts in force lack a section that other sections of the same Act cite at least 3 times: the Income-tax Act 1961 (section 143, cited 51 times, and 264, 212, 116 and others), the Insolvency and Bankruptcy Code (271, 272, 326), the Companies Act 2013 (90, 271, 435), the Prevention of Money-Laundering Act (24, burden of proof; 15, 25), the Competition Act, the Insurance Act, the Patents Act, the Merchant Shipping Act. The list is in `docs/SECTION-COVERAGE.md`.
* **The CPC 9 / 11 pattern (a number held by Order rules while the section's own text is absent)** is flagged for 134 Acts in force that file 3 or more different provisions under one number; it is confirmed for CPC only (phrase search) and NOT for the others. The detector marks CPC 9 and 11 only as collisions, not as absent, so it under-counts this class.
* **Limits.** N is a lower bound (a missing tail is invisible; Schedule rows can push N up; an omitted or repealed number counts as missing). The same checker run independently on the owner's earlier repo's data found 38,508 expected and 8,881 missing for Acts in force; this finds 38,294 and 9,584.

**What this means for `core/coverage.json` (not changed; lane C owns the generator):** it says the Central Acts are held. That is true of 1,568 Acts and not of their sections: about a fifth of the section numbers in force Acts have no text anywhere, and a lookup by section number can miss text that is stored inside a neighbour's chunk. The number for the owner: **about 20 to 25 of every 100 sections of the Acts in force are not in the data**, concentrated in 154 Acts that hold under half of theirs.

## 27. Check 4 cannot ask who is speaking: a limit of the check, not a defect in it (5 Nov 2026, measured)

### What check 4 is asked

`core/prompts/claim_support.txt`, in full: "Does the passage support the sentence? Reply with exactly one word: supports, partly or does_not_support."
It is given the sentence and the passage. Nothing in the question concerns who in the passage is saying the words.

### What it did on the 79 pairs (section 22)

| Pairs | Count | Real check, first pass |
|---|---|---|
| Not the court's holding (a party's argument, a rejected argument, a lower court's holding, an order on the facts) | 5 | **5 supports**, again 5 of 5 on the second pass |
| Judged defective in some way (the five, a remark stapled to a marker, an obeyed injection, an empty marker) | 8 | **1 removed** (the empty marker), 7 passed |
| Judged sound or merely garbled by list-splitting | 71 | 1 removed (q056 S6, disputed: section 25 of the Evidence Act quoted in a judgment that says it does not apply there) |

### Why this is a limit and not a defect

The check does what it was specified to do. A passage that recites counsel arguing a proposition does support that proposition, in the sense the
question asks; "supports" is a property of the words. Who is speaking is a property of the passage's structure (a party's submission, a rejected
argument, a lower court's reasoning, the court's own holding). A model that answers "supports" there is answering the question it was asked correctly. Retuning
the prompt will not move this: the five pass because the question has the wrong shape for them.

The remedy is not a better prompt for check 4 either. "Is this the court's holding?" is a legal judgement. Putting it to the same kind of model that
passed the five adds a fifth check that can be talked round (section 22). The instrument is the advocate review (`docs/ADVOCATE-REVIEW-PACK.md`).

### What this does to `CLAUDE.md` §5

§5 says the tick does **not** mean "the quote is the holding, or the AI's summary is right". Until section 22 that was a caveat. It is now a number:

| | |
|---|---|
| Pairs the mechanical checks passed where the cited words were not the court's holding | **5 of 79 (6.3%; 95% Wilson interval 2.7% to 14.0%)** |
| Drafts affected | 3 of 35 that carried a marker |
| Checks that could have caught it | none: checks 1 and 2 test the label and the record, check 3 fired on one of the five and passed it (the words are in the record), check 4 passed all five |

One run, one model, practice-fixture retrieval, one non-advocate reader of the five (section 22 limits). The advocate pack sizes it properly; this section does not
claim the 6.3% is the true rate. It claims that **the shipped checks, taken together, pass this class at a rate of about 100% of the instances found.** No product wording was changed:
"Record found in dataset" does not claim a holding, and the user-facing text is the owner's.

## 28. What asking the writer to quote statute wording verbatim would cost: measured, not applied (5 Nov 2026)

The case for it: check 3 fires on 6.3% of cited pairs (section 25), so for most cited sentences the only mechanical guarantee is check 4, a model's opinion, and section 27 shows check 4 cannot ask who is speaking.
This section sizes the lever the way A137 sized strict mode. **Nothing is applied: `core/prompts/answer.txt` is unchanged.** The owner decides.

### What was changed and how it was measured

One sentence added to a scratch copy of the answer prompt, after "Quote only words that appear exactly in the passage":
*"When a sentence states what an Act, section, rule or article provides, quote the provision's own words exactly as they appear in the passage, inside quotation marks, and end the sentence with the source id. Do not paraphrase a provision."*

Same harness as A137 (`evals/real_run.py` pipeline, real `gemini-3.5-flash-lite` as the writer, the 1,398-record practice fixture, fake word-overlap gate and claim check), on the **current branch**. The branch has changed since A137, so **136** questions now reach the writer (A137: 95),
and the comparator is a fresh run of the A137 prompt on the same code, not the A137 numbers. Check-3 figures come from replaying each run's saved drafts through the real `verify()` with check 4 forced to "supports", which isolates checks 1 to 3 and A137 strict from the fake check 4.

**One run per prompt.** A second run of each failed: the eval key's project reached its monthly spending cap (HTTP 429, "exceeded its monthly spending cap"). Nothing was retried on another key. So there is no noise estimate from this session; A137 saw run-to-run swings (6 questions cited under one prompt only and 2 under the other, of 33), so treat small differences as unresolved. The large ones below are not small.

### Side by side

| | A137 prompt | Verbatim-quote prompt |
|---|---|---|
| Questions that reach the writer | 136 | 136 |
| Non-empty drafts | 42 | 45 |
| **Answers served** (`answered`) | **38** | **27** |
| Marked sentences drafted | 77 | 80 |
| ...of which carry a quoted span | 6 (7.8%) | **67 (83.8%)** |
| Drafts with a quoted sentence | 5 | 34 |
| Quoted spans; median length | 6; 3 words | 75; 20 words |
| **Sentences removed by check 3** | 1 | **30 (45% of the 67 quoted)** |
| Drafts emptied by check 3 alone | 1 | **13** |
| ...still emptied if the stored-text damage below were excused | 0 | 8 |
| Answers served whose text keeps a quote | 4 | 21 |
| Sentences kept that carry a verified quote | 5 of 76 (6.6%) | 37 of 50 (74%) |
| Answered under both prompts | 23 | 23 |
| Answered under A137 prompt only / under variant only | 15 / 4 | |
| Words on the 23 answered under both | 1,872 (median 53) | 1,473 (median 35): **-21%** |

The 15 / 4 mixes check-3 emptying with ordinary model variance that this session could not size. 13 drafts were emptied by check 3 alone under the variant against 1 under the A137 prompt, so most of the 11-answer net loss is check 3, but not all of it is proven to be.

### Why check 3 removes 45% of the quoted sentences

Classified on the **letters only** (so markers, digits, spacing and case do not count), 30 removals:

| Cause | Sentences |
|---|---|
| The quote's words are all present in order, but the stored text has list markers (`_a_`, `_ii_`), footnote numbers, margin letters or odd spacing inside them | 16 |
| Words present with a few letters garbled in the stored text (`po er`, `Magi5 trate`, `investiJation`, `thecheque`, `Indianlaw`) | 2 |
| **Stored-text damage subtotal** | **18 (60%)** |
| The quote skips, joins or changes words (the model, not the record) | 11 (37%) |
| Capital letter against lowercase at the start of a sentence | 1 |

By quote length: 12 words or fewer, 5 of 24 fail (21%); 13 to 30 words, 14 of 28 (50%); 31 or more, 12 of 23 (52%). The classification is automatic and I read a sample, not all 30.

### A147: the OCR exposure, measured on these passages

A-SC3's detector (`scan/sc/ocr_noise.py`) on the passages cited in these runs: **6.5%** of 12-word windows carry an artifact under the A137 prompt and **6.1%** under the variant, inside A147's 3.5% to 9.4%. That rate understates what a quote suffers, for two reasons the table shows: the variant's quotes are long (a median of 20 words, so a quote crosses many windows),
and the damage includes **markdown list markers in statute text (`_a_`) and inline footnote numbers**, which that detector does not look for. So the cleaning A147 describes (clean a copy of the record text, never loosen check 3) is a **precondition** for this lever: with the 18 stored-text removals excused, check 3 would remove 12 of 67 instead of 30 and 8 drafts would still be emptied instead of 13. The remaining 12 are the model quoting inexactly. Check 3 was not loosened and is not proposed to be.

### What it would and would not buy

- **Buys:** check 3 would back 74% of the sentences that survive instead of 6.6%: "these words are in the record" would be mechanically proved for most statutory sentences.
- **Does not buy:** anything against the section 22 class. The five misattributed pairs (q067 x3, q088, q091) are judgment passages, not statutory provisions, and the variant only asks for verbatim quotation of provisions. q088 already carried quotation marks and passed. A verbatim quote proves the words are in the record; it does not prove who is speaking (section 27).
- **Costs (this retrieval, one run):** 11 fewer answers served of 38 (-29%), 21% shorter on the answers served both times, and, until the record is cleaned, 18 honest quotes stripped.

My read, for the owner to take or leave: do not apply it before the record-text cleaning of A147 exists; after it, the lever is worth re-measuring on a real retrieval, because it hardens the statutory wording check and costs the answers that quote inexactly. It is not the answer to section 22.

### Found on the way: a possessive apostrophe fails check 3 (not fixed)

`core/verify.py` `_unbalanced_quotes` counts `‘` and `’` and fails closed when they differ, so a sentence with a curly possessive and no opening quote (`the nation’s economy`) is removed as `quote_not_found`. It cost 1 of 79 pairs in the A137 run (q100) and 0 in the other three runs' ~280 marked sentences, so it is rare in this sample; real judgments use curly apostrophes more.
It is the opposite of a fabrication, and it is a class: any sentence whose only quote-like mark is a possessive `’`. A narrow fix exists (treat a `’` between two letters as an apostrophe, not a mark) with a class-wide test; **it is not applied**, because it changes check 3 and you have refused loosening it. It needs the owner's word.

