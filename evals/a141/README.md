# evals/a141

The measurements behind the A141 cost picture ([`docs/A141-COST-PICTURE.md`](../../docs/A141-COST-PICTURE.md)): what it would cost to load the 2,865,144 cases that DATA-GAPS section 19 found in the parquet and in no Qdrant collection. **Pipeline step 5 (Search); nothing here changes behaviour.** The scripts that read the missing set live in `scan/` next to the scan that found it.

Run from the repo root as modules. Large inputs and outputs stay outside git, in `~/qdrant-kanoon/a128_confirm/` (`A136_DATA` overrides it) and `~/qdrant-kanoon/coverage_gap/`.

| # | Script | Answers | Needs | Spend |
|---|---|---|---|---|
| 1 | `scan/missing_set.py` | cases, chunks, characters, chunks per case and decision year of the missing set, per court; the 10,112 INSC (national court) chunks matched by id against A129; Kerala tokens per character | the lane A scan's saved hashes (`coverage_gap/scan`, `coverage_gap/parquet`), the parquet on the SSD, the copy instance for the staged INSC collection | none |
| 2 | `scan/missing_tokens.py` | the Voyage tokens of every missing chunk, counted locally with Voyage's published tokenizer; refuses to run unless it first reproduces two billed figures from the token ledger exactly | `tokenizers`, `pyarrow` | none |
| 3 | `scan/missing_cases_sample.py` | 20 whole-missing cases drawn uniformly at random, first 500 characters each, for a person to read | as 1 | none; writes OUTSIDE the repo (party names) |
| 4 | `evals/a141/sparse_only_sim.py` | what a chunk with a BM25 vector and no dense vector gets back on the known-item harness | the copy instance holding `a128_multicourt`; the stored A136 query vectors | none |
| 5 | `evals/a141/load_cost.py` | BM25 encode speed, upsert speed and disk per point for sparse-only and dense+sparse points, on a real sample of the missing chunks | `fastembed`, `pyarrow`; the copy instance | none |
| 6 | `evals/a141/model_choice.py` | `voyage-4-lite` against `voyage-4` against `voyage-4-large` as the DOCUMENT model, on the A136 known-item queries (`prepare`, `embed`, `build`, `run`) | the copy instance; `VOYAGE_API_KEY` line of the repo `.env` for `embed` only | **`embed` only: about $0.37 at list price, behind `--go` and a $0.60 cap** |

| 7 | `evals/a141/model_choice_missing.py` | the same three-model comparison on 2,000 chunks drawn uniformly from the MISSING SET, with short chunks kept in the targets; also splits results at the median target length (`sample`, `validate`, `queries`, `embed`, `build`, `run`). The paraphrase writers' prompt is saved in `paraphrase_prompt.md` | as 6, plus `scan/missing_rows.py` for the cache | **`queries` and `embed`: about $0.29 at list price, behind `--go` and a $0.45 cap**; the exact document tokens are printed before any spend |
| 8 | `scan/missing_rows.py`, `scan/missing_bands.py` | the cached row positions of the missing chunks; the cases by length band with count, share, cost to include, and three random examples of each (written outside the repo) | as 1 and 2 | none |

Not A141 measurements but built in the same session: `evals/labelling/` (the labelling pack for the 100 stub questions; see its own docstrings) and `data/voyage_token_count.py` (the exact token count; `COSTS.md` "Exact token counts").

Environments: steps 4 and 6 run in the repo `.venv` (`qdrant-client`). Steps 1, 2, 3 and 5 need `pyarrow`, and 2 and 5 also `tokenizers` and `fastembed`; the repo `.venv` has none of those, so they were run from a Python 3.12 scratch environment (`uv venv`, then `uv pip install numpy pyarrow fastembed voyageai`; add `pydantic pydantic-settings litellm qdrant-client httpx openpyxl` for `evals/labelling/`). The repo `.venv` is Python 3.14, where `fastembed` did not install (the install ran for minutes and was stopped). The `dev` extra is not changed for this: adding `pyarrow` and `voyageai` to it is a decision for the owner of `pyproject.toml`.

Only `model_choice.py embed` can spend, it is the only script here that makes a Voyage call, and it goes through `adapters/voyage.py` (A127). `tests/test_a141_cost_picture.py` pins the aggregation and the refusals.
