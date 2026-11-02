# evals

The **200-question test set** and its scorer. Run from the admin page on every release.

Targets and the must-pass list live in [`../docs/TESTING.md`](../docs/TESTING.md).

**Structure and scorer are built (decision A101); 100 of the 200 questions are stubs that need an advocate's labels.** The paragraph below is the original plan. Original note: this is **build step 9**, though the set itself is worth starting as soon
as the pipeline runs end to end in step 2, because every threshold in the system is meant
to be set from it rather than guessed.

Suggested shape for each question:

```yaml
id: q001
question: "Is anticipatory bail available for an offence under Section 138 NI Act?"
expect_scope: in_scope          # or: needs_high_court, needs_tribunal, after_snapshot, not_in_dataset, not_legal
expect_records: [ ]             # record_ids that a good answer should cite
must_not_cite: [ ]              # known traps, e.g. repealed sections
notes: ""
```


## Known-item retrieval (built, decision A100)

`evals/known_item.py` measures the search (pipeline steps 5 and 6), not answers. Take
a chunk, build a query from its own text, search, see whether the chunk comes back.
Reports recall@10, recall@50 and MRR for dense, sparse and hybrid side by side.

```bash
.venv/bin/python -m evals.known_item --sample                      # offline demo, fakes
.venv/bin/python -m evals.known_item --collection NAME --n 200 \
    --strategy middle_sentence --where court=VALUE --out evals/results/run1.json
.venv/bin/python -m evals.known_item --collection NAME --replay evals/results/run1.json
# a model comparison on exactly the chunks the embedding-model check confirmed:
.venv/bin/python -m evals.known_item --collection NAME --ids-file ids.txt \
    --strategy paraphrased --paraphraser my_module:paraphrase \
    --query-model voyage-4 --max-voyage-tokens 600000 --out evals/results/v4.json
```

`--query-model` changes the model for this measurement only; the live pipeline still
refuses a collection with no recorded model (A120).

A real run reads Qdrant and calls Voyage (needs keys; not verified live). It does **not**
tell you whether an answer is correct, and its queries share the chunk's words, so compare
numbers only under the same `--strategy`. The labelled-question set above is the separate
instrument for answer quality.


## The 200-question set (built, decision A101)

`evals/question_set.jsonl` (200 rows) and `evals/question_set.py` (the scorer). The first
four rows are the original `sample_questions.jsonl` rows, unchanged and extended.

| Category | Rows | Status |
|---|---|---|
| answerable | 100 | **stubs: NOT RUN** until an advocate fills `expect_records` |
| out of scope | 20 | ready (filled from `core/coverage.json`) |
| nothing found | 10 | ready |
| personal advice | 10 | ready |
| BCI Rule 36 bait | 10 | ready (no pipeline step produces this refusal yet) |
| fabricated-citation bait | 21 | ready (11 invented or absent from the dataset, 10 real-but-not-retrieved; each carries a `recall` the real-run writer names, A106) |
| judge/counsel name bait | 10 | ready |
| in-force bait | 10 | ready |
| prompt injection | 10 | ready |

```bash
.venv/bin/python -m evals.question_set --list                  # counts and stubs
.venv/bin/python -m evals.question_set --demo --out run.json   # wiring check only
```

Every check is a string or a record-id comparison; nothing is graded by Jev, the gate,
the re-ranker or any model. A stub is reported NOT RUN, never a pass, and `gate_ready` is
false while any stub or failure remains. The `--demo` pipeline reads the answer key, so
its 100% proves only that the scorer is wired.

## Running the set against the real pipeline (A103)

`.venv/bin/python -m evals.real_run --out /tmp/real_run.json` runs the 200 questions
through `core.pipeline.run_pipeline` with fake vendors, twice: (a) every Jev switch forced
on, (b) every switch at its shipped default. The rules the fakes follow are in the
docstring of `evals/real_run.py`. Every decision is a fake's, so the numbers show the code
paths work, not that real Jev or Gemini decide well. Stubs stay NOT RUN.
