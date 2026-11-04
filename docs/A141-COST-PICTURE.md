# A141 cost picture: loading the cases the search index does not hold

**Written 4 Nov 2026. A table, not a recommendation: every figure is labelled _Measured_, _Checked_ or _Estimate_, and every Estimate says what would turn it into a measurement and what that costs.** Companion to `DECISIONS.md` A141 and `DATA-GAPS.md` §19. It is a new file because `COSTS.md` has another owner; the exact-token-count method it relies on is recorded in `COSTS.md` ("Exact token counts"). Prices are the vendor's published list prices, fetched 4 Nov 2026 (_Checked_): `voyage-4-lite` $0.02, `voyage-4` $0.06 and `voyage-4-large` $0.12 per million tokens, standard; the Batch API is 33% cheaper (lite $0.0134, voyage-4 $0.0402). Rupees use **₹85 to the dollar, an assumption** (the figure the repo has used so far), not a quoted rate. The free 200M-token allowance is **not** applied to any price below (see §1).

**What is in scope.** The 2,865,144 cases of §19 less the Supreme Court: the owner dropped it from A141 because A129 already embedded its 10,112 chunks (§2). So the set priced here is **2,864,410 cases, 4,193,024 chunks**.

## 1. Spent to date (from the token ledger)

The ledger is `~/qdrant-kanoon/kerala_fix/token_ledger.jsonl`: one row per request, tokens as the Voyage API returned them. It starts at 13:00 on 3 Nov. **Measured** tokens; the dollar column is tokens × list price.

| What | Tokens | List price |
|---|---:|---:|
| Kerala re-embed (A123, 217,766 chunks, `voyage-4`) | 270,093,721 | $16.21 |
| Supreme Court embed (A129, 10,112 chunks, `voyage-4-large`) | 9,546,375 | $1.15 |
| Model comparison on the evaluation corpus (3 models × 2,000 chunks) | 5,594,712 | $0.37 |
| Model comparison on missing-set chunks (3 models × 2,000 chunks, plus 1,178 queries) | 4,281,189 | $0.29 |
| Rate-limit probes (3 Nov) | 2,092,827 | $0.16 |
| Everything else (tests, verification, evaluation queries) | 1,027,896 | $0.07 |
| **Total** | **292,636,720** | **$18.24 (about ₹1,550)** |

- **What was actually billed is not known.** Voyage's pricing page gives "the first 200 million tokens" free for each of the three models and does not say whether that is per model or one pool. If per model, the bill is about **$4.54**; if one pool, about **$6.20**. _Estimate (a range, not a point)._ **What settles it:** the Voyage billing dashboard, free, one look.
- **Not in the ledger:** work before 13:00 on 3 Nov (`COSTS.md` §2b puts it at about 3M tokens, an _Estimate_, at most a few cents); and the Voyage calls the real pipeline makes itself (query embedding and rerank) for the 100-question labelling run, which does not write to the ledger (_Estimate_, a few cents; settle from the dashboard).
- The Kerala line is $16.21, not the $16.36 A141 quotes; the ledger figure is used.

## 2. What the missing set is made of

All **Measured** (`scan/missing_set.py`, `scan/missing_tokens.py`; both reconcile to §19's 2,865,144 cases and 4,202,934 chunks exactly or refuse to report).

- **Chunks per case: 1.46**, not the 2.7–3 A141 estimated. 93.8% of cases are a single chunk. Kerala is 1.03.
- **Tokens: 3,422M** for the 4,193,024 chunks, counted with Voyage's own tokenizer. The count was checked against three billed runs and matched **to the token each time** (§7). Characters: 9.66 billion, a mean of 2,299 per chunk.
- **Supreme Court: dropped from scope.** Its 10,112 parquet-only English chunks are exactly the 10,112 A129 embedded: **10,112 of 10,112 chunk ids identical**, and all 10,112 are already in `kanoon_v1`. A129's $1.15 closed it. (That is on the copy instance's `kanoon_v1`; the original `legal_corpus_v1`/`v2` still lack them.) Its 734 whole cases and 9,910 chunks are left out of every figure below.

| Court | Whole cases missing | Chunks | Chunks per case | Single-chunk cases | Tokens | Tokens per chunk |
|---|---:|---:|---:|---:|---:|---:|
| Rajasthan | 732,511 | 1,596,831 | 2.18 | 84.0% | 1,591M | 996 |
| Punjab & Haryana | 652,833 | 906,975 | 1.39 | 99.8% | 937M | 1,033 |
| Orissa | 408,974 | 409,441 | 1.00 | 100.0% | 142M | 346 |
| Calcutta (appellate side) | 123,966 | 186,384 | 1.50 | 87.8% | 132M | 706 |
| Uttarakhand | 79,117 | 134,987 | 1.71 | 77.0% | 99M | 736 |
| Madhya Pradesh | 243,679 | 244,378 | 1.00 | 99.9% | 95M | 388 |
| Allahabad | 67,857 | 94,370 | 1.39 | 83.4% | 84M | 887 |
| Jharkhand | 176,690 | 177,748 | 1.01 | 99.9% | 78M | 441 |
| Kerala | 111,528 | 115,343 | 1.03 | 99.1% | 74M | 642 |
| Karnataka | 102,616 | 105,639 | 1.03 | 98.9% | 67M | 631 |
| All other courts (17) | 164,639 | 220,928 | 1.34 | | 124M | 561 |
| **All, Supreme Court excluded** | **2,864,410** | **4,193,024** | **1.46** | | **3,422M** | **816** |

### Chunk length across all 4,202,934 chunks (Voyage tokens; ≈ 3.5 characters per token)

| Chunk length | Chunks | Share | Tokens | Share of tokens |
|---|---:|---:|---:|---:|
| 0-99 tokens | 14 | 0.0% | 0M | 0.0% |
| 100-199 tokens | 92,727 | 2.2% | 16M | 0.5% |
| 200-399 tokens | 1,172,612 | 27.9% | 360M | 10.5% |
| 400-799 tokens | 1,421,068 | 33.8% | 774M | 22.6% |
| 800-1,199 tokens | 651,258 | 15.5% | 651M | 19.0% |
| 1,200-1,599 tokens | 507,980 | 12.1% | 705M | 20.6% |
| 1,600+ tokens | 357,275 | 8.5% | 925M | 27.0% |

## 3. The length bands (the owner draws the line; none is proposed here)

Whether to load short orders decides **what law the product covers**, so it is the owner's decision and the answer belongs in `core/coverage.json` (A51/O7), where an exclusion must be written as an explicit entry and shown on the coverage page. Silently dropping a band is not an option. **Length is the judgment text in characters** (the largest `char_end` over a case's chunks; the stored header line is not counted). Real examples from each band (first 500 characters of three random cases per band) are in `~/qdrant-kanoon/coverage_gap/missing_bands_examples.md`, kept outside the repo because it holds party names. _Measured._

| Judgment text | Cases | Share of cases | Chunks | Tokens | Share of tokens | Cost to include this band: voyage-4 batch | lite batch | Largest courts in the band |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 250-499 chars | 97,395 | 3.4% | 97,395 | 18M | 0.5% | $0.71 | $0.24 | Orissa 33%, Madhya Pradesh 28%, Punjab & Haryana 12% |
| 500-999 chars | 861,844 | 30.1% | 861,844 | 251M | 7.3% | $10 | $3.37 | Punjab & Haryana 40%, Orissa 18%, Rajasthan 14% |
| 1,000-1,499 chars | 806,318 | 28.1% | 806,318 | 352M | 10.2% | $14 | $4.71 | Punjab & Haryana 23%, Rajasthan 20%, Orissa 16% |
| 1,500-1,999 chars | 636,276 | 22.2% | 636,276 | 363M | 10.6% | $15 | $4.87 | Rajasthan 22%, Punjab & Haryana 17%, Orissa 14% |
| 2,000-2,999 chars | 194,544 | 6.8% | 194,545 | 158M | 4.6% | $6.37 | $2.12 | Rajasthan 65%, Calcutta (appellate side) 15%, Uttarakhand 8% |
| 3,000-3,999 chars | 85,443 | 3.0% | 85,444 | 97M | 2.8% | $3.90 | $1.30 | Rajasthan 64%, Calcutta (appellate side) 12%, Uttarakhand 10% |
| 4,000-7,999 chars | 97,840 | 3.4% | 197,351 | 187M | 5.5% | $7.53 | $2.51 | Rajasthan 65%, Uttarakhand 10%, Allahabad 9% |
| 8,000+ chars | 85,484 | 3.0% | 1,323,761 | 2,005M | 58.4% | $81 | $27 | Rajasthan 67%, Uttarakhand 10%, Calcutta (appellate side) 8% |

(This table includes the Supreme Court's 734 cases: 2,865,144 cases in all. Almost all of them have 8,000 characters or more, since they average about 13 chunks, but that was not checked case by case. Dropping them changes no band's cases or tokens by 1% or more.)

**Where to draw the line, as a table.** "Line at N" means: load every case with N characters or more of judgment text, leave the rest out.

| If the line is drawn at | Cases left out | Cases loaded | Tokens | voyage-4 batch | lite batch |
|---|---:|---:|---:|---:|---:|
| 250 characters or more | 0 (0.0%) | 2,865,144 | 3,431M | $138 (₹11,725) | $46 (₹3,908) |
| 500 characters or more | 97,395 (3.4%) | 2,767,749 | 3,414M | $137 (₹11,665) | $46 (₹3,888) |
| 1,000 characters or more | 959,239 (33.5%) | 1,905,905 | 3,162M | $127 (₹10,806) | $42 (₹3,602) |
| 1,500 characters or more | 1,765,557 (61.6%) | 1,099,587 | 2,811M | $113 (₹9,605) | $38 (₹3,202) |
| 2,000 characters or more | 2,401,833 (83.8%) | 463,311 | 2,447M | $98 (₹8,363) | $33 (₹2,788) |
| 3,000 characters or more | 2,596,377 (90.6%) | 268,767 | 2,289M | $92 (₹7,821) | $31 (₹2,607) |
| 4,000 characters or more | 2,681,820 (93.6%) | 183,324 | 2,192M | $88 (₹7,490) | $29 (₹2,497) |
| 8,000 characters or more | 2,779,660 (97.0%) | 85,484 | 2,005M | $81 (₹6,850) | $27 (₹2,283) |

**What the table shows, with no recommendation attached.** Short orders are cheap and long judgments are the cost: cases under 1,000 characters are 33.5% of the missing cases and about 8% of the tokens; the 85,484 cases of 8,000 characters or more are 3.0% of cases and 58.4% of tokens. A length cut-off is therefore a decision about coverage, and it moves the price very little until it is set high. Every number here is _Measured_, except that the dollars assume the batch discount applies to the whole job (_Checked_ for the 33%, not yet seen on an invoice).

## 4. The dense options, priced

Dense = embed every chunk with Voyage so it is findable by meaning as well as by keyword. Tokens are **Measured** (§7). Prices are the list price of those tokens: `voyage-4-lite` and `voyage-4`, batch and standard. `voyage-4-large` is not priced: the owner ruled it out (§5). Nothing is recommended.

| Option | Cases | Chunks | Tokens | lite, batch | lite, standard | voyage-4, batch | voyage-4, standard |
|---|---:|---:|---:|---:|---:|---:|---:|
| **A. Everything** (all High Courts, Supreme Court excluded, see §2) | 2,864,410 | 4,193,024 | 3,422M | $46 (₹3,898) | $68 (₹5,818) | $138 (₹11,693) | $205 (₹17,453) |
| **B. Last ten years** (decided 2016 or later) | 2,187,850 | 3,308,501 | 2,855M | $38 (₹3,252) | $57 (₹4,853) | $115 (₹9,755) | $171 (₹14,559) |
| **C. Three largest courts** (Rajasthan, Punjab & Haryana, Orissa) | 1,794,318 | 2,913,247 | 2,670M | $36 (₹3,041) | $53 (₹4,539) | $107 (₹9,123) | $160 (₹13,616) |

- The length-band options in §3 are further options on the same basis.
- **The three largest courts are 62.6% of the cases but 78% of the tokens**, because Rajasthan and Punjab & Haryana have long chunks (about 1,000 tokens each against about 350 for Orissa).
- **The free allowance changes none of these by more than a few dollars.** `voyage-4` is already past its 200M; `voyage-4-lite` has about 196M left, worth at most $3.9 at the standard price, and the vendor page does not say it applies to batch jobs.
- **Batch limits (_Checked_):** up to 100,000 inputs per batch file, 1 billion tokens in flight across jobs, a 12-hour window. 3.4 billion tokens is therefore several rounds, not one submission.
- _Estimate:_ the total is exact only if Voyage bills exactly the tokens counted. It did on all three checks (§7). **What would make it a measurement:** submit a 100,000-token batch first (about $0.004 at lite batch) and read the invoice line.

## 5. The model comparison

Two runs of the same method: 2,000 chunks embedded under all three models at 1,024 dimensions with `input_type: "document"`; three scratch collections with identical ids, payload and BM25 vectors that differ only in the dense vector; one `voyage-4` query vector throughout (the production setting, A136); 250 targets; cluster bootstrap over targets. Cells are the difference from `voyage-4` in points with a 95% interval. **Measured.** Spend: $0.37 and $0.29 at list.

**Run 1: the A136 evaluation corpus** (chunks averaging 3,260 characters, 932 tokens; 1,161 queries).

| Metric (both query styles) | voyage-4 recall | lite minus voyage-4 | large minus voyage-4 |
|---|---:|---:|---:|
| dense @10 | 84.4% | -0.6 [-1.6, +0.4] | -0.8 [-1.9, +0.3] |
| dense @50 | 92.1% | -1.0 [-1.9, -0.2] | -0.4 [-1.4, +0.6] |
| hybrid @10 | 95.0% | -0.8 [-1.5, -0.2] | -0.2 [-0.7, +0.3] |
| hybrid @50 | 97.9% | -0.5 [-1.1, -0.1] | +0.2 [-0.2, +0.5] |

**Run 2: chunks drawn uniformly from the missing set** (mean 707 tokens, median 532; 250 targets; 1,178 queries; 98% of the corpus could yield a query, so the short chunks are in the targets).

| Metric (both query styles) | voyage-4 recall | lite minus voyage-4 | large minus voyage-4 |
|---|---:|---:|---:|
| dense @10 | 78.7% | -3.1 [-4.5, -1.8] | -1.4 [-2.6, -0.1] |
| dense @50 | 88.5% | -0.5 [-1.5, +0.4] | -0.2 [-1.2, +0.9] |
| hybrid @10 | 89.3% | -0.6 [-1.4, +0.2] | +0.3 [-0.3, +0.9] |
| hybrid @50 | 95.5% | +0.0 [-0.4, +0.5] | +0.2 [-0.4, +0.8] |

| Run 2, dense @ 10 only | lite minus voyage-4 | large minus voyage-4 |
|---|---:|---:|
| Sentence-style queries | -2.5 [-4.2, -0.7] | -1.3 [-3.0, +0.3] |
| Paraphrase queries | -4.0 [-6.2, -1.8] | -1.4 [-3.6, +0.8] |
| Shorter half of the targets (≤ 527 tokens) | -2.5 [-4.4, -0.5] | -1.8 [-3.7, -0.2] |
| Longer half | -3.8 [-5.7, -2.1] | -0.9 [-2.6, +0.9] |

**What the two runs say, stated narrowly.**
- **Large is not better than `voyage-4` as a document model on this corpus, in either run.** Dense @10 is lower in both (−0.8, interval crossing zero, then −1.4, interval just excluding it); hybrid is indistinguishable (−0.2 and +0.3, both crossing zero). It costs twice the standard price. That contradicts the vendor's framing of the large model as the quality tier and is worth having on record. The owner has ruled it out.
- **Lite is clearly behind on dense in run 2** (−3.1 @10, interval clear of zero, past the owner's two-point test) and is nearly level on hybrid (−0.6 @10, crossing zero; −0.0 @50). Run 1 showed a smaller dense gap (−0.6) with a small, distinguishable hybrid gap (−0.8 [−1.5, −0.2]). The run-2 dense gap is **not concentrated in short text**: shorter half −2.5, longer half −3.8. The cause of the larger gap on missing-set text is not known.
- **Neither run has a rerank step.** Step 5 returns the top 50 and step 6 (`rerank-2.5-lite`, a reranker that reads the query and passage text) keeps 10. Whether reranking absorbs an @10 difference is **unmeasured**, so these figures must not be read as showing that it does. @50 is the number that bounds what the reranker can ever surface.
- The corpora are 2,000 chunks, small next to the real collection, and recall is higher than it would be at scale. Differences between models, not absolute recall, are the point.
- The owner's decision is `voyage-4` at batch rates. The numbers do not contradict it; they do not make the case for anything else.

## 6. Loading with no embedding API at all (BM25 only)

BM25 vectors are computed on the laptop. A133 did 1,024,068 Act points at zero spend. **What it does and does not buy:**

**Recall of a sparse-only chunk, on the known-item harness** (the A136 evaluation corpus, 18,399 chunks, with the dense vector removed from the 250 targets only, so each target is a sparse-only chunk next to ordinary dense+sparse ones; the same 1,161 stored queries; no spend). _Measured on that corpus; not measured at production scale._

| Hybrid recall of the target | Ordinary chunk (dense + sparse) | Sparse-only chunk | Difference |
|---|---:|---:|---:|
| Sentence-style queries, @10 | 95.8% | 95.5% | -0.3 [-0.7, +0.0] |
| Paraphrase queries, @10 | 69.1% | 41.7% | -27.4 [-31.5, -23.1] |
| Paraphrase queries, @50 | 84.8% | 61.2% | -23.5 [-27.5, -19.5] |
| Both styles, @10 | 85.5% | 74.8% | -10.7 [-12.3, -9.1] |

**This is a free half-fix.** On queries that share words with the passage (sentence-style) a sparse-only chunk is found as well as any other. On natural-language questions that do not, it falls from 69% to 42% at rank 10. Today these chunks are at 0%.

**Compute and disk** for all 4,202,934 chunks of the missing set (Supreme Court included in this load estimate), from a sample of 91,675 real missing chunks (mean 2,245 characters, from 16 courts):

| | Measured on the sample | Extrapolated to 4,202,934 chunks (_Estimate_) |
|---|---|---|
| BM25 encoding, one process | 2,995 chunks per second | **23 minutes** |
| Upsert, sparse-only points | 5,515 points per second | 13 minutes |
| **Compute, sparse-only, in all** | | **about 0.6 hours** |
| Disk, sparse-only points | 9.5 KB per point in the segments | **about 41 GB** (about 44 GB with the write-ahead log) |
| Upsert, dense+sparse points (random vectors, so indicative) | 1,341 points per second | 52 minutes |
| Reference: the served collection `kanoon_v1` | 11.98 KB per point (Supreme Court and Acts) | |

- **A sparse-only point takes the same disk as a full point.** In a collection configured like `kanoon_v1` (a dense vector declared), Qdrant reserves the dense-vector slot for every point whether or not it has a dense vector: the dense storage was 471 MB in both scratch collections of 91,675 points. So sparse-only saves the embedding spend and **none of the disk**. The disk figure above is the same for the dense options.
- The dense index graph adds little on disk: 6 MB for 91,675 points, about 66 bytes per point, so about 0.3 GB at 4,202,934 points (_Estimate_, linear; the graph will be larger per point at scale).
- Running more than one process was **slower** than one (1,769 against 2,995 chunks per second), so the single-process rate is the one used.
- RAM at serving time, for the dense index in particular, was **not measured**.
- _Estimates:_ the extrapolations are linear from a 91,675-chunk sample. **What would make them measurements:** load all 4,202,934 chunks into a scratch collection on the copy instance. No API cost; roughly an hour of compute and 41 GB of the 132 GB free on the laptop.

## 7. Exact token counts (what makes the dollars above Measured)

`data/voyage_token_count.py` counts the tokens Voyage will bill, locally and free, with the published tokenizer. **Billed tokens are the local count minus one per text.** Checked against billed runs from the ledger:

| Check | Local count | Billed (ledger) | Difference |
|---|---:|---:|---:|
| 2,000 evaluation-corpus chunks | 1,864,904 | 1,864,904 (each of the three models) | **0** |
| 10,112 Supreme Court chunks, from the parquet text (A129) | 9,546,375 | 9,546,375 | **0** |
| 2,000 missing-set chunks (run 2) | 1,414,980 | 1,414,980 (each of the three models) | **0** |

Method, limits and use are in `COSTS.md`. Before this, tokens were estimated from characters; three measured ratios (0.254, 0.286 and 0.357 tokens per character) differ by ±17%, so a character-based total for the missing set would have been anywhere from 2.5 to 3.5 billion tokens. The measured total is 3.43 billion (Supreme Court included).

## 8. Estimates, and what would turn each into a measurement

| Figure | Label | What would turn it into a measurement | Cost |
|---|---|---|---|
| Billed amount to date ($4.54 to $6.20 against $18.24 at list) | Estimate, a range | Read the Voyage billing dashboard | Free |
| Pre-ledger spend (about 3M tokens) | Estimate | The same dashboard, by date | Free |
| Voyage calls made by the real pipeline in the labelling run | Estimate | The same dashboard | Free |
| The batch discount applies to the whole backfill (33%) | Checked on the vendor page, not on an invoice | Submit a 100,000-token batch and read the invoice line | About $0.004 at lite batch |
| ₹85 to the dollar | Assumption | Use the rate on the day the job is paid | Free |
| Compute time for the BM25 load (0.6 hours) | Estimate (linear from 91,675 chunks) | Load all 4,202,934 chunks into a scratch collection on the copy instance | No API cost; about an hour; 41 GB of disk |
| Disk for the load (about 41 GB) | Estimate (same) | The same full load | Same |
| Dense upsert time (52 minutes, random vectors) | Estimate, indicative only | Load with the real vectors after they exist | Part of the embedding job |
| RAM to serve the dense index | Not measured | Build the index on the copy instance and read resident memory | No API cost; hours |
| Sparse-only recall at production scale (measured on 18,399 chunks) | Measured small, unmeasured large | Add the 455,755 `kanoon_v1` chunks as distractors in the scratch collection and re-run the same queries | No API cost (the vectors and query vectors already exist); scripting and hours of compute |
| What a model gap would cost corpus-wide (the lite option) | Not measured; arithmetic only: run 1's hybrid @10 gap of 0.8 scaled by the backfill's 13% share of chunks to 18% of cases is 0.1 to 0.15 points | Advocate-phrased queries over the launch collection (PRD-v2 gate item 29) | Advocate time plus a fraction of a rupee of embedding |
| Whether reranking absorbs the @10 model differences | Unmeasured (the harness has no rerank step) | Add the rerank step to the harness and re-run | Rerank tokens at the vendor's rerank price, which was not looked up here; small |
| Why the lite gap is larger on missing-set text than on the evaluation corpus | Unknown | A third corpus drawn by court to separate court mix from length | About the cost of run 2 (₹24 at list, _Estimate_) |

Everything not in this table is **Measured** or **Checked** as labelled where it appears.

## 9. Where things are

- Code: `scan/missing_set.py`, `scan/missing_tokens.py`, `scan/missing_rows.py`, `scan/missing_bands.py`, `scan/missing_cases_sample.py`, `data/voyage_token_count.py`, `evals/a141/` (README there), tests in `tests/test_a141_cost_picture.py`.
- Results (outside the repo): `~/qdrant-kanoon/coverage_gap/` (`missing_set.json`, `missing_tokens.json`, `missing_bands.json`) and `~/qdrant-kanoon/a128_confirm/` (`a141_*`, `a141m_*`, `a141x_*`).
- Cases to read (party names, so outside the repo): `~/qdrant-kanoon/coverage_gap/missing_cases_sample.md` (20 random whole-missing cases) and `missing_bands_examples.md` (3 per length band).
- The scratch collections the measurements built on the copy instance (`a141_sparse_only_sim`, `a141m_*`, `a141x_*`, `a141_disk_*`) are left in place.
