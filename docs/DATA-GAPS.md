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

## 9. About half of `acts_india` has wrong keyword vectors

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

**Priority:** the 19,835 broken Central Act points inside `kanoon_v1` are the ones actually
being served, and they are a twelve-second job. The other ~504,600 are not in the copy yet and
can be repaired as part of whatever copies them.

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

### Update (2 Nov 2026, later): it is not one model per collection

The same reproduction test, run on 111 stored chunks across every group (stored dense vector
against a fresh `input_type=document` embedding of the stored text; a chunk "reproduces" under
the one model that gives cosine 0.999 or better):

| Group | Chunks | `voyage-4` | `voyage-4-large` | `voyage-4-lite` |
|---|---|---|---|---|
| `legal_corpus_v2` Supreme Court (in `kanoon_v1`) | 23 | 0 | 23 | 0 |
| `acts_india` Central | 7 | 0 | 7 | 0 |
| `acts_india` state | 37 | 24 | 13 | 0 |
| `acts_india` regulatory | 26 | 24 | 2 | 0 |
| `legal_corpus_v1` High Court | 8 | 5 | 2 (Delhi, Patna) | 1 (Allahabad) |
| `legal_corpus_v2` High Court | 10 | 6 | 0 | 4 (Karnataka, Rajasthan x2, Punjab and Haryana) |

- **Every original collection mixes models**, and the mix follows the document or the ingestion
  batch (a court, an Act), not the collection. In `legal_corpus_v2` High Court, Kerala, Madhya
  Pradesh, Orissa and Manipur are `voyage-4` while Karnataka, Rajasthan and Punjab and Haryana
  are `voyage-4-lite`. State Acts mix `voyage-4` and `voyage-4-large` inside one state.
- **How exact:** `voyage-4` reproduces at 0.99998, `voyage-4-lite` at 0.99995 to 0.99997,
  `voyage-4-large` at 0.9991 to 0.9996, except two SEBI regulations that reproduce **exactly**
  (1.000000) under `voyage-4-large`. So the 0.999 offset is not a property of that model: it
  appears on some `voyage-4-large` chunks and not others. Still unexplained.
- **Why it matters:** the same text embedded by two models agrees only to about 0.91 to 0.96
  cosine, so a query embedded with one model scores chunks built with another lower, and the
  ranking is quietly biased toward the chunks that happen to share the query's model. Whether
  that bias matters in practice is not measured (no retrieval-quality metric exists yet).
- **What the code now does:** `VOYAGE_EMBED_MODELS` (per collection). Only `kanoon_v1`, which
  holds the Supreme Court set and the Central Act points, is listed (`voyage-4-large`, 30 of 30
  sampled). Any other collection is refused rather than defaulted. The original collections are
  deliberately absent. Open: choose how mixed collections are searched (several query
  embeddings, one chosen model, or re-embedding) before serving High Court chunks or state Acts.
- **Sampling limit:** 111 chunks, in clusters: the shares above are indications, not rates.
