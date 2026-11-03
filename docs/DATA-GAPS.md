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

**Priority — settled 3 Nov 2026.** The 19,830 Central Act points in `kanoon_v1` are **already repaired** (verified read-only: 0 of 74,484 would change; `COSTS.md` §2b). The other ~504,600 sit in the original `acts_india`, which **nothing serves** — only Central Acts are in the copy. **Do not repair them now:** it would mean writing to an original for no present benefit, and §17's rule exists precisely to keep originals untouched. **Instead, the repair belongs in whatever copies them.** Any job that builds a serving collection containing state Acts or regulators must recompute their BM25 sparse vectors on the way in, and say in its report how many it fixed. If that step is skipped, roughly half of those provisions reach users with keyword search finding **nothing** for them — which is how they were found in the first place.

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

**Not tested:** a *mixed* corpus, where a matched and a mismatched document compete in one ranking.
This shows only that changing the query model does not hurt a single-model corpus.

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

**Working answer: the per-court config at $0.** Hybrid is what ships, and hybrid loses nothing
measurable to a mismatched query.

### Two findings in that report that deserve more weight than they got

1. **Dense vectors unrelated to their own text.** 2 of 50 Kerala v2 chunks scored cosine about 0
   under every model. At that rate, ~4% of Kerala's 3.1M chunks are **unfindable by dense search
   at all** — not ranked badly, invisible. It rests on two chunks and is unverified. But section 9
   measured ~48% of `acts_india` carrying raw term counts where BM25 weights belong, so broken
   vectors are an established failure mode in this data, not a fluke. A second class of them in a
   different collection is plausible and cheap to measure. **For the trust promise this is worse
   than any ranking bias:** a chunk that cannot be retrieved cannot be cited, so the user is told
   "not in our dataset" about something the dataset holds.

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
- **Every other court is clean:** 0 of 2,694 across v1 and v2, 95% upper bound 0.13%. Overall
  0.69% of the 31.0M High Court points, all of it Kerala v2.
- **The text is fine in all 31** — 430 to 4,211 characters, no replacement characters. A bad
  vector, not bad text.
- **The sparse vector is intact in all 31.** Hybrid finds every one of them. **Nothing is
  unreachable by any path**, so the severity is roughly half what section 13 feared: degraded
  ranking, not invisibility, and a citation to such a chunk still verifies.
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
| Old vs new vector | cosine max 0.133, mean -0.002: all 217,766 old vectors were unrelated to their text |
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
Running it needs the 850 check-4 query texts re-embedded with `voyage-4` (the first run did not save
the query vectors): about 40,000 tokens, under a cent. **Not run**, because the instruction was no
Voyage calls.

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

