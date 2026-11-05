# Paraphrase-question writer prompt (A141 model comparison on the missing set)

Given to each writer (a Haiku sub-agent) together with one input file `a141x_qgen/in_<k>.json` holding `[{"id": "...", "passage": "..."}, ...]`. The writer returns `a141x_qgen/out_<k>.json`: an object mapping each `id` to a list of exactly two question strings. A136's equivalent prompt was not saved; this one is, so the paraphrase arm can be regenerated.

```
You are helping test a legal search engine. For each passage in the input file, write TWO different
questions that a lawyer or law student could ask whose answer is in that passage, but phrased the way a
person would ask a research question, NOT copied from the passage.

Rules, all of them mandatory:
- 8 to 40 words, ending with a question mark.
- Do not copy any run of four or more consecutive words from the passage.
- No digits anywhere (no section numbers, years, case numbers).
- Do not use any person's or company's name, or any capitalised word from the passage, except these:
  Court, Act, Article, Constitution, India, Indian, High, Supreme, Section, Code, State, Government.
- Ask about the legal point or the facts in general terms ("Can a bail application be withdrawn with
  liberty to renew it?"), not about the named parties.
- The two questions for one passage must not be near-duplicates of each other.
- If a passage is a routine procedural order with little legal content, still write two questions about
  what the order did (for example, an adjournment, a withdrawal, a notice, a direction).

Read the input file, write the output file, and reply with only the path you wrote.
```

Questions that break a rule are discarded by `evals/a141/model_choice_missing.py validate` (the A136 validator); how many were discarded is reported there.
