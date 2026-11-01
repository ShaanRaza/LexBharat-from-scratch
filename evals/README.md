# evals

The **200-question test set** and its scorer. Run on every release (from the admin page
in production). Targets and the must-pass list: [`../docs/TESTING.md`](../docs/TESTING.md).

## What exists today

| File | What it is |
|---|---|
| `runner.py` | Loads questions, runs each through the real 11-step pipeline with **fake** services, reports the launch numbers |
| `sample_questions.jsonl` | 9 sample questions (real, lookup, trap). **Not** the frozen 200-question set |
| `sample_corpus.json` | 4 made-up sample records the fakes search over |

```bash
python -m evals.runner                        # run the sample set
python -m evals.runner --questions my.jsonl --corpus my_corpus.json
python -m evals.runner --gate                 # exit code 1 if a launch gate is missed
```

It reports: **verified-citation rate** (gate 98% or higher), **answers with a removed
citation** (gate under 0.5%), **forbidden citations shown** (gate: zero), and how many
questions behaved as expected, split by kind.

Questions `s008` and `s009` use `fake_model: invent_citation` / `wrong_quote`: the fake
model misbehaves on purpose so you can watch the verifier remove the bad citation. That
is why the sample set reports "launch gates met: NO". That is expected; it proves the
scorer sees failures.

## What is NOT here yet

- The real 200 questions (100 interview questions, 50 Act lookups, **50 traps**). They are
  frozen and need the advocate advisor's sign-off first.
- Real services. Everything is faked, so **answer quality, speed and cost are not measured**.
- Correctness grading (two advocates, blind) - a human process, not code.

## Question format (one JSON object per line)

```json
{"id": "q001", "kind": "real", "question": "...", "expect_scope": "in_scope",
 "expect_outcome": "answered", "expect_records": [], "must_not_cite": [], "notes": "",
 "fake_model": "honest"}
```

`kind` is `real`, `lookup` or `trap`. `expect_outcome` is `answered`, `out_of_scope` or
`not_found`. `fake_model` is for fake runs only and is ignored once real services exist.
