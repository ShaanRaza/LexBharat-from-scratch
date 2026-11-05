# Citation verifier

The single most important component. If this is weak, nothing else matters.

It runs **after** the model finishes writing and **before** the user sees any citation.

## The four checks

A citation passes only if **all four** pass.

| # | Check | What it catches | Cost |
|---|---|---|---|
| 1 | **Retrieved for this question** | The source ID was one of S1–S8 given to the model *this turn*. A real case the model remembered from training but that was not retrieved **fails**. This stops the model citing a real but irrelevant case | Free, Python |
| 2 | **Record exists** | That passage's `record_id` exists in `kanoon_v1` | Free, Python lookup |
| 3 | **Quotes match** | Any words in quotation marks appear in that record's text exactly, after tidying spaces and punctuation | Free, Python |
| 4 | **Claim supported** | Jev rates whether the cited passage supports the sentence it is attached to: supports / partly / does not support | Jev (Gemini paid tier in upload chats) |

**Checks 1–3 always run, Jev up or down.** Check 4 is the only one that depends on an
outside decision service, and it degrades to the Gemini fallback.

Check 4 goes **beyond the PRD**, which requires only that a record exists and quotes match.
It narrows — but does not remove — the "is the summary right?" gap: a passage can support a
sentence and the case can still be bad law.

## On failure

1. The citation is **removed** from the answer.
2. The answer carries a note that one authority could not be verified.
3. A row goes to `invented_citation_log`: question, model, the failed citation, and the
   reason — one of `not_retrieved`, `record_missing`, `quote_not_found`,
   `claim_not_supported`, or `store_unavailable`.

`store_unavailable` is check 2 failing because the record store could not be asked (a
timeout or an outage), not because the record is absent. Behaviour is the same as a
missing record (fail closed: the citation is removed, no tick), but the log says what
happened, so a slow database never reads as the model inventing a citation.

**Launch metric:** the share of answers with a removed citation, for any of the **four**
citation reasons (not `store_unavailable`, which is tracked on its own), must be
**under 0.5%**. It is shown on the admin page and checked on every release
against the 200-question test set.

## What the tick means — and does not

The tick is the core trust claim, so it states only what the checks can prove.

| The tick means | The tick does NOT mean |
|---|---|
| The cited case or Act section exists as a record in the dataset, matched by its record ID | The case is good law. It may have been overruled, distinguished or reversed on appeal |
| Words in quotation marks appear in that record's text | The quoted passage is the holding, or that the AI's summary of it is right |
| The link goes to the record's `pdf_url` (judgments) or `source_url` (Acts) | The link works today, or the text is current law. The data is a snapshot (**v2026.08**) |
| A citation string, if stored, is shown exactly as recorded | The citation string is correct or complete. Filled for **100% of Supreme Court chunks and 0% of High Court chunks** (Measured), so High Court answers will show none |
| The cited passage was retrieved for this question, so the AI cannot cite a record it never saw | **That other relevant cases were not missed.** The verifier says nothing about recall |
| Jev rates the passage as supporting the sentence it is cited for | **That a lawyer reviewed the point.** Jev is a model check and can be wrong |

**Wording shown to users:** "Record found in dataset", with the data-as-of date and a short
link to this definition.

**Ticks are per citation**, never one badge for the whole answer.

## Display rule for citation strings

For Supreme Court cases, the citation string (for example an SCR reference) is shown
**exactly as stored**, labelled "as recorded in the dataset", and is **never retyped or
reformatted by the AI**.

## Tests

The verifier has tests that must pass before any deploy (rule 6 in
[`../CLAUDE.md`](../CLAUDE.md)). At minimum, each of the four failure reasons needs a test
that proves the citation is removed and logged. See [`TESTING.md`](TESTING.md).
