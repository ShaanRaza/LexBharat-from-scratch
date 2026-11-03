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
measurements. The per-court config cuts the exposure by roughly a factor of ten at either end. Nothing here
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

**What this says about the per-court config: it is load-bearing, not optional.** An earlier version of this
paragraph called it "unnecessary rather than merely wrong-grained"; that was wrong and is withdrawn. It rested
on two tests whose corpora were almost entirely `voyage-4` (Bombay v1; the Kerala eval) and on sentence-style
queries. The corpus is not like that: **73% of the sampled High Court chunks are not `voyage-4`** (about 54%
volume-weighted), **7 courts show no `voyage-4` chunk at all** in any sampled group (Patna, Chhattisgarh,
Sikkim, Jharkhand, Jammu and Kashmir, Karnataka, Rajasthan), and **1,543 of the 2,640 sampled chunks (58%) sit
in court groups with no `voyage-4` chunk** (see the table below). Under one `voyage-4` query model that mismatch
reaches most of the corpus; a per-court majority query model cuts it to **7.6%** (about 8% volume-weighted). That
is the whole job the config does, and at those shares it matters. The dense deficit it avoids is 6 to 8 points
per mismatched chunk (above). Whether *hybrid* also depends on it was tested ("The question-style retest", below): it does, at
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
against a corpus believed single-model; see the end of this section. The config itself is load-bearing.)*

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
pairs. Whitespace-only and real-content differences: none in either. A record fetched by either point
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

