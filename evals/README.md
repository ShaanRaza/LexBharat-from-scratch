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
