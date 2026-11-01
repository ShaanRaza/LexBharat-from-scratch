# Dataset

KanoonBuddy is built on **open-india-law** from Vaquill AI — a static snapshot
(**v2026.08**) of official government sources, CC BY 4.0.

Unless marked otherwise, every figure here is **Measured** on the local copy with DuckDB
across all 75 parquet files on 6 October 2026.

## What the copy holds

| Item | Figure |
|---|---|
| Supreme Court cases | **37,014** |
| All courts | 15,693,540 distinct `case_id` in 26 judgment files |
| Total chunks | 32,572,660 |
| Legislation | 10,112 Acts + 12,152 regulatory instruments = **22,264**, in 1,098,269 chunk rows |
| Regulators | 12 |
| Law Commission reports | 77,080 rows, 558 instruments |
| Tribunals | **None** (Measured) |
| District and trial courts | Not included |
| Files | 75 parquet (26 judgment, 37 legislation, 12 regulation), ~50 GB of text |
| Vectors | ~440 GB on disk; full snapshot 463.6 GB |

### Qdrant collections on the local machine

| Collection | Points |
|---|---|
| `legal_corpus_v1` | 19,595,718 |
| `legal_corpus_v2` | 11,823,753 |
| `acts_india` | 1,098,577 |
| **Total** | **32,518,048** |

Embeddings are **Voyage voyage-4, 1024 dimensions, cosine distance**. Any semantic query
must use the same model, or the vectors are meaningless.

### Findings from inspecting the local Qdrant copy (2 Nov 2026)

Reported by the session that runs the Qdrant copy. **Not re-run from this repo** (this
session did not touch Qdrant): treat as Measured by that session, to re-check when the
copy finishes.

| Finding | Evidence | What to do |
|---|---|---|
| **Judgment sparse vectors reproduce exactly** with FastEmbed `Qdrant/bm25` (16 of 16 sampled) | Measured (small sample) | Queries must use `query_embed()`, **not** `embed()` (that is the document side). `adapters/qdrant.py` does |
| **`acts_india`: 19,835 of 74,509 Central Act points (26.6%, full scan) do not match the encoder.** Their sparse vectors are plain integer counts, so keyword search silently misses them | Measured (full scan of Central points) | Repair script `data/sparse_fix.py` (`plan`, `apply --confirm`, `restore`). **Not yet run on live data** |
| The earlier "52% of `acts_india`" figure | Came from a flawed sample | **Unknown.** Do not quote it |
| **Dense vectors are mixed**: a judgment chunk matches voyage-4 exactly (cosine 1.0000); a Central Act chunk matches **voyage-4-large** (0.9994) | Measured, **one chunk each only** | More testing pending on the copy. Until then a voyage-4 query vector may be slightly off against Act chunks |
| **`language_code` is mostly missing** and uses uppercase `"EN"` | Measured | Select English Supreme Court chunks with `court = "Supreme Court of India"`. The store refuses a `language_code` filter |
| `legal_corpus_v2` holds 11.8M points, mostly outside v1 | Measured | v1 scope is about **371,159** Supreme Court points plus **74,509** Central Act points |
| The PRD's claim that keyword search must be **built from scratch** is wrong for judgments | Measured: the sparse vectors already exist and reproduce | Build step in `docs/DATA-MODEL.md` (compute BM25) is only needed for Acts that fail the check |
| **Filtered scans on unindexed payload fields over the big collections time out** | Measured | Create payload indexes on `court`, `jurisdiction`, `section_number`, `act_status` before real use |
| The Supreme Court **translations (about 742,000 chunks)** are real non-English text and were **not embedded** | Measured | Consistent with v1 scope (English only). Do not serve them |

## At launch

Only the **Supreme Court and `acts_india`** are served, from one new collection. Everything
else is held but not served. Launch size: about **6 to 20 GB** (Estimate, from the Measured counts of
371,159 Supreme Court points and up to 1,098,577 `acts_india` points); memory with scalar
quantization well under the earlier 4–5 GB estimate (Needs verification by load test).

## Field quality — read this before trusting any field

| Field | Fill rate | Problem |
|---|---|---|
| `source_url`, judgments | **0.0%** | Use `pdf_url` instead |
| `source_url`, legislation | 100% | Also has `mirror_url` |
| `citation`, Supreme Court | **100.0%** | No problem — the verifier can check real strings like "[1979] 3 S.C.R. 453" |
| `citation`, all 25 High Courts | **0.0%** | The verifier must fall back to record existence and quoted text |
| `disposition` | 98.8% | **577 different values** — a High Court problem. The SC concentrates in ~10 |
| `judges` | 32.7% | Sampled values were extraction garbage ("another", "apply for bail") |
| `petitioner` / `respondent` | 99.9% | Often counsel names or sentence fragments, not party names |
| `section_number`, legislation | 98.5% | No problem — section lookup works directly |
| `in_force`, legislation | 100% | No problem **as a field** — but see `act_status` below |

**Consequence: never display judges or party names.** A tool sold on trust cannot show
wrong names.

### The `act_status` trap

`act_status` is filled for only **74,484 rows across 1,568 acts** (in force 59,596,
repealed 14,604, spent 284), against 1,098,269 rows and 22,264 acts in total.

**Working decision:** show the in-force flag **only** on acts whose `act_status` is filled,
and label every other Act result **"in-force status not checked"**.

## Coverage is shallower than the court list suggests

The dataset card's "Earliest" column is the single oldest document in a court, not where
coverage begins. Share of each court's cases dated before 2015:

| Court | Before 2015 | Card's earliest year |
|---|---|---|
| **Supreme Court** | **78.0%** | 1950 |
| Telangana | 45.4% | 1963 |
| Bombay | 45.0% | 1953 |
| Kerala | 39.9% | 1950 |
| Patna | 33.0% | 1967 |
| Himachal Pradesh | 31.7% | — |
| Punjab and Haryana | 30.1% | — |
| Gujarat | 29.6% | — |
| Chhattisgarh | 26.4% | — |
| Gauhati | 22.2% | — |
| Rajasthan | 17.6% | — |
| Delhi | 15.8% | 1960 |
| Karnataka | 12.9% | — |
| Madras | 7.4% | 1997 |
| Orissa | 1.0% | 1992 |
| Jammu and Kashmir | 0.9% | — |
| Allahabad | **0.0%** | 1992 |
| Andhra Pradesh | **0.0%** | 1995 |
| Calcutta | **0.0%** | 1960 |

Calcutta is advertised as 1960–2025 yet has **zero** cases before 2015. Delhi has one case
in 1960 and six in 1997. Seven High Courts are not in the audit summary (Needs
verification).

**For historical research this corpus is a Supreme Court archive with a thin High Court
layer. Any marketing claim of "all 25 High Courts since 1950" would be false.**

This is also why phase 2 is **Bombay, Telangana and Kerala** — the three deepest archives.
Delhi (15.8%) and Madras (7.4%) are the shallowest of the four originally planned, though
Delhi carries disproportionate commercial, constitutional, tax and IP work, so practical
relevance may outweigh archive depth. The interviews settle it.

## Known discrepancies — do not paper over these

| Item | Finding |
|---|---|
| **`case_id` is not one per case** | Rajasthan: 1,056,767 `case_id` against 308,342 distinct `case_number`. Patna: 1,614,939 against 504,632. So 15.7M counts **case records**, not cases. **Never compete on document counts** |
| Judgments vs the dataset card | The card claims 12,848,644 judgments; disk holds 15,693,540 distinct `case_id` — 22% more |
| Three judgment counts in circulation | 12.8M+ (Vaquill's India page), 32.5M chunks (its GitHub), 15,693,540 cases (Measured). Reconcile in weeks 1–2 |
| `acts_india` point count | Qdrant holds 1,098,577 points against 1,098,269 parquet rows. The 308 difference is **unexplained** (Needs verification) |
| **Text without vectors** | Either ~1,153,189 chunks (3.5%) or ~55,000 (0.2%) exist as text with no vector, depending on whether the 32,572,660 total includes the 1,098,269 legislation rows. Count rows per judgment file against points per collection |
| **Checksums** | `SHA256SUMS.json` and `totals.json` each describe **one** file (Kerala). **74 of 75 files have no published checksum** — request per-file checksums from Vaquill |
| Snapshot v2026.08.1 | Published but not held. Its headline change is `source_url` on 83.3% of rows (Competitor claim). Weigh against mirror speeds of 0.03–11.6 MB/s |

## Licence

| What | Licence |
|---|---|
| Data | **CC BY 4.0** — credit required |
| Code (the project's scrapers) | Apache-2.0 |
| Underlying legal text | Government work, Copyright Act **s.52(1)(q)** |

**Credit string, on every result, stats page, Act page and share card:**

```
Data: Open India Law by Vaquill AI, CC BY 4.0
```

Link each judgment through its `pdf_url` (a Cloudflare R2 link) and each Act through its
`source_url`. **Judgments have no `source_url`.** Have a lawyer confirm commercial use.

Personal details (victim names, phone numbers, account numbers) are already removed
according to the dataset card. Plan a takedown request process; the card names
`contact@vaquill.ai` for redaction requests.

## Dependence on Vaquill

The whole product rests on one organisation continuing to publish this dataset.

| If Vaquill | What happens | What we do |
|---|---|---|
| **Stops publishing** | The v2026.08 snapshot already held stays usable; no new judgments arrive | Run the project's scrapers ourselves (Apache-2.0) or go to the court sites directly |
| **Changes the licence** | New terms apply only to new releases. CC BY 4.0 cannot be withdrawn for a copy already received (a lawyer must confirm) | **Keep the licence text, dataset card and checksums exactly as downloaded, with the date. Keep an offline copy of the data and the scraper code** |
| **Starts charging** | Same — the existing snapshot is unaffected | Ask now what bulk extraction costs; keep a contingency line |
| **Builds a competing product** | Vaquill already sells an end-user legal AI product and holds the same corpus | Compete on product, distribution and trust, not on data |

**Do this now:** email Vaquill to confirm in writing (a) whether the India API licence
permits caching responses and serving them to end users, including on public indexed
pages, (b) what bulk or daily-sync licensing costs for the India judgment corpus and
whether it includes incremental deltas, and (c) whether a judgments endpoint is on the
India roadmap.

## The Vaquill API — optional upgrade, not a dependency

**Judgments are not available through any Vaquill API.** The India API is legislation only.
The local corpus is the only route to judgments short of a data-licensing contract.

| | Our local snapshot | Vaquill API |
|---|---|---|
| Instruments | 22,264 (Measured) | 64,179 (Competitor claim) |
| Section-level retrieval | Yes, 98.5% filled | Yes, 745,970 sections |
| Amendment history | In-force status only | Yes, with corresponding-provisions mapping |
| Freshness | Frozen at v2026.08 | Daily full-corpus sync under licensing; price not published |
| **Cost per query** | **Free — payload filter** | 1 credit = US$0.01; a search is 2 credits ≈ ₹1.76 |

**Decision: serve legislation from our own data at zero per-query cost.** At 3,000 monthly
visits, API search would cost ₹2,600–₹5,300 a month — the free tier would become the
largest variable cost at exactly the traffic we are trying to grow.
