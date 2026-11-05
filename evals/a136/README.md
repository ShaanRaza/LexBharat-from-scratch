# evals/a136

The scripts behind **DECISIONS A136**: the query model stays `voyage-4`. A single `voyage-4-large` query vector was tested against a single `voyage-4` vector on 250 fresh targets and 1,161 queries. Dense @10 +1.6 [+0.3, +2.9] replicated; hybrid @10 -0.1 [-0.9, +0.7] did not. This is the evidence under PRD-v2 gate items 28 and 29, and it is also what A138 reads as "not detectable with this harness" for hybrid. **Pipeline step 5 (Search) measurement; nothing here changes behaviour.**

Run every script **from the repo root, as a module**: `.venv/bin/python -m evals.a136.c_analyze`. Install with `pip install -e ".[dev]"` (`fastembed`, for `c_sparse`, is in the `dev` extra).

## Where things are

| What | Where | In git? |
|---|---|---|
| Code, this README | `evals/a136/` | yes |
| The 1,161 queries (`c_queries.json`), the per-query ranks (`c_results.json`), the court facets used to weight by volume (`court_facets.json`), the paraphrases the Haiku writers returned (`paraphrases/out_*.json`) | `evals/a136/results/` (about 0.5 MB) | yes |
| Large inputs and outputs (about 15 MB): `c_qvec.npy` (9.5 MB, the paid query embeddings), `a128_corpus_meta.json` (2.8 MB), `a128_targets.json` and `c_targets.json` (1 MB each), `c_sparse.json`, `qgen/in_*.json` (the passages given to the paraphrase writers) | `~/qdrant-kanoon/a128_confirm/` on the owner's laptop, or wherever `A136_DATA` points | **no, one laptop only** |

`c_sparse.json` and `c_queries.json` can be regenerated from the committed files; `c_qvec.npy` can be regenerated for about Rs 0.65 but a fresh Voyage call is not promised to be bit-identical, so keep the stored one.

## Run order

| # | Script | Needs | Spend | Re-run on 4 Nov 2026? |
|---|---|---|---|---|
| 1 | `c_targets.py` | the original Qdrant on 6333, read only, through `orig_ro.py` (a whitelist: count, scroll, query, facet on `legal_corpus_v1/v2` and `acts_india`; no write route; hard stop, no retry); `a128_corpus_meta.json` and `a128_targets.json` in `A136_DATA` | none | **No** (needs the live original) |
| - | Haiku paraphrase writers: read `qgen/in_*.json`, write `qgen/out_*.json` | a model | small | **Not scripted**; the prompt is not saved with these files |
| 2 | `c_validate.py` | `c_targets.json` and `qgen/out_*.json` in `A136_DATA` (copy `results/paraphrases/` to `A136_DATA/qgen/`) | none | **Yes**: rebuilt `c_queries.json` byte for byte (500 paraphrases received, 54 rejected, 715 sentence + 446 paraphrase = 1,161 queries) |
| 3 | `c_embed.py` | `VOYAGE_API_KEY` line of the repo `.env` (read, never printed); goes through `adapters/voyage.py`; appends to `~/qdrant-kanoon/kerala_fix/token_ledger.jsonl` | **about Rs 0.65** | **No** (spend) |
| 4 | `c_sparse.py` | `fastembed` (BM25) | none | **Yes**: all 1,157 stored sparse query vectors reproduced, 0 differences (`fastembed` 0.9.1) |
| 5 | `c_run.py` | the copy instance on 127.0.0.1:7333 holding `a128_multicourt` (18,399 chunks, 24 courts, built by the A128 scripts in `~/qdrant-kanoon/a128_eval/`, which are **not** in this folder); `c_qvec.npy`, `c_sparse.json`, `c_targets.json` | none | **No** (needs the live copy instance) |
| 6 | `c_analyze.py` | only the committed `results/c_results.json` and `results/court_facets.json` | none | **Yes**: output identical to the 4 Nov run, all 39 lines |

**Offline check, no laptop needed:** `.venv/bin/python -m evals.a136.c_analyze` reproduces every A136 figure from the committed files. `c_analyze.py` takes an optional path to another results file. If `c_run.py` is run again it writes `A136_DATA/c_results.json`; copy it to `results/` to make the new run the committed evidence.

## What this does not establish

The corpus is the 18,399-chunk sample, not the launch collection, and both query styles are model-written or sentence-style (A138: the harness is at its hybrid ceiling). The remaining measurement is PRD-v2 gate item 29: the launch collection's real model mixture with advocate-phrased queries.
