# core/prompts

Prompt templates, kept as files rather than inline strings.

Rule 7: each pipeline step is a separate function with a fixed input and output, so each
step's prompt should be separately readable, diffable and swappable.

Expected files as the pipeline is built:

| File | Step | Notes |
|---|---|---|
| `rewrite.md` | 2. Rewrite | Turns the message + context into one standalone query; extracts Act, section, case number, year |
| `summarise.md` | 1. Remember | Refreshes the rolling summary of older turns |
| `answer.md` | 8. Answer | **Must instruct: use only the given passages S1–S8 and the reviewed background notes, and put a source ID after every point taken from one** |
| `answer_upload.md` | 8. Answer, upload chats | Must label "your document says" separately from what the dataset's sources say (that label is built from `core/coverage.json`, never typed) |

Jev's decisions are **fixed choice lists**, not prose prompts — they belong in
`adapters/decisions.py` with their choice sets, per the Tech Stack's safeguards.

## Rules

- Prompts never hard-code the product name — it comes from `PRODUCT_NAME` config.
- The answer prompt must never be loosened to "improve" answer quality. If answers are
  thin, the fix is retrieval or the knowledge notes, **not permission to use untrusted
  knowledge**.
- Changing a prompt changes answer behaviour: re-run the 200-question test set.
