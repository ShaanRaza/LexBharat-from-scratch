# evals

The **200-question test set** and its scorer. Run from the admin page on every release.

Targets and the must-pass list live in [`../docs/TESTING.md`](../docs/TESTING.md).

Not built yet — this is **build step 9**, though the set itself is worth starting as soon
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
