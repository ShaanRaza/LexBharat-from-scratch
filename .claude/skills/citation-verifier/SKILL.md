---
name: citation-verifier
description: Use when touching the citation verifier, the verification badge or tick, citations, source IDs S1-S8, the invented-citation log, the answer-or-refuse gate, or pipeline steps 7 (gate) and 9 (verify). Also use when changing what a user sees next to a cited case, when an answer cites something, when adding High Court data, or whenever a change could let an unverified authority reach a user. Not for general retrieval tuning that does not touch verification.
---

# Citation verifier

This is the product. An answer with a fabricated citation is worse than no answer. Full
detail: `docs/CITATION-VERIFIER.md`.

## Before you change anything

Ask: **could this let an authority reach a user without passing all four checks?** If yes,
stop and say so.

## The four checks — all must pass

1. **Retrieved for this question** — the source ID was one of S1–S8 given to the model
   *this turn*. A real case the model recalled from training **fails**.
2. **Record exists** — the `record_id` exists in the launch collection.
3. **Quotes match** — quoted words appear in that record's text, after normalising spaces
   and punctuation.
4. **Claim supported** — Jev rates supports / partly / does not support.

**Checks 1–3 are free Python and must run whether Jev is up, down or timing out.** If your
change makes any of 1–3 conditional on Jev, it is wrong.

## Non-negotiables

- A failed citation is **removed**, the answer notes one authority could not be verified,
  and a row goes to `invented_citation_log` with one of: `not_retrieved`, `record_missing`,
  `quote_not_found`, `claim_not_supported`, or `store_unavailable` (check 2 could not ask
  the store: fail closed, own reason, not counted in the invented-citation metric).
- **Nothing citation-shaped streams before the single post-verification `citations` event.**
  A user must never see a citation appear and then vanish.
- Ticks are **per citation**, never one badge for the whole answer.
- Supreme Court citation strings are shown **exactly as stored**, labelled "as recorded in
  the dataset". **The AI never retypes or reformats them.**
- High Courts have **no citation strings** (0.0% filled) — the verifier falls back to
  record existence and quoted text.
- Badge wording is **"Record found in dataset"** plus the data-as-of date. Do not reword it
  without updating `docs/UX-COPY.md`.

## What the tick must never be made to imply

That the case is good law · that the quote is the holding · that the AI's summary is right ·
that the link works today · that the citation string is correct · **that other relevant
cases were not missed** · that a lawyer reviewed it. Jev is a model check and can be wrong.

## Before you call it done

- [ ] A test exists for each of the four failure reasons: citation removed **and** logged
- [ ] A test proves checks 1–3 still run with Jev off and with Jev timing out
- [ ] A test proves no citation leaves before the `citations` event
- [ ] The 200-question test set still gives a verified-citation rate **≥ 98%**
- [ ] Removed-citation rate still **under 0.5%**

Both numbers are launch gate conditions. If you cannot run the test set, say so plainly
rather than claiming the change is safe.
