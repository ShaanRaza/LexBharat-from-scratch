# Design note: the empty-text guard for the future Supreme Court scraper's ingest

Status: **design only**. Nothing here is built, and nothing in `data/` was touched.
Written by the SC lane, 4 Nov 2026. Evidence labels as in CLAUDE.md §9.5.

## Why it is needed

The verifier fetches a cited record by `chunk_id` (`adapters/qdrant.py:473`) and takes its `text`
(`core/verify.py:300`, `_record_text`). An empty string is not `None`, so **check 2 (record exists) passes
for a record whose text is empty**. Check 3 then fails only if the sentence has quoted words; a sentence
with no quotation marks goes on to check 4 with nothing behind it, and a "Record found in dataset" tick
could sit on a record with no readable words. `docs/DATA-GAPS.md` §3 names this.

**Today the hole is not open (Measured, 4 Nov 2026).** All 381,271 served Supreme Court chunks have a body
of at least 5 alphabetic words after the `Case: ... Section: ...` header (0 below; 1 chunk between 5 and
19). The risk is a future load, so the guard belongs where chunks enter, not in the verifier.

## Where it sits

In the **loader of the future SC scraper**, between "parse a judgment into chunks" and "write points",
before anything is embedded (so a refused chunk costs no vendor call). It is a data-quality gate, not a
pipeline step, and it does not touch any verifier check.

```
scrape -> parse -> chunk -> [GUARD] -> embed -> write to the collection
                              |
                              +-> refused chunks -> a quarantine file + a count in the run report
```

## The rule

A chunk is **refused** unless all of these hold:

1. `text` has a body after the first blank line (the header is `Case: ...\nSection: ...\n\n`).
2. The body has at least **5 alphabetic words** of 2+ letters (`[A-Za-z]{2,}`). Same helper the audit used:
   `scan/sc/no_text_audit.py: body_words`. The threshold is the audit's, and is a floor that catches empty
   and noise-only chunks, not a quality bar. (Whether 5 is the best floor is **not verified**: the served
   data has nothing between 0 and 5 to test it against.)
3. `chunk_id` is not already in the collection (the original data holds 4,871 duplicate ids; this is the
   same gate for them).
4. `case_id` has at least one chunk that passed rule 2. A case with no readable chunk is **not loaded at
   all** (this is the "4,068 no text" shape, caught at the case level).

Non-English text: a body of non-Latin script has no `[A-Za-z]` words and is refused by rule 2. That is
intended for now (v1 serves English only; the 1,329 unserved judgments are such cases). When Hindi ships,
the rule must count words in the right script per `language_code`; change it then, in this file first.

## What a refusal does

- The chunk is **not written**; it goes to `quarantine/<run>/<case_id>.jsonl` with the reason code
  (`empty_body`, `too_few_words`, `duplicate_chunk_id`, `case_has_no_readable_chunk`).
- The run report lists counts per reason and the case ids. A run with any `case_has_no_readable_chunk`
  exits non-zero, so it cannot be promoted by accident.
- Nothing is deleted from the source.

## How it is tested

1. Unit: an empty body, a header-only chunk, a 4-word body, a 5-word body, a duplicate id, a case whose
   chunks are all empty. The 4-word and 5-word cases pin the boundary.
2. Property: any chunk the guard accepts, when fetched back, makes `_record_text` return text with
   at least 5 words (round trip through the fake vector store).
3. Standing check on the served collection: `python scan/sc/no_text_audit.py ...` must report 0 chunks
   under the floor. Run it after every load, before promotion.

## What was ruled out

Rejecting empty text inside `core/verify.py` (for example `if not record_text: record_missing`). It
would work and is one line, but it changes check 2, which belongs to the trust lane and is not to be
touched for a data problem. If the trust lane wants a defence in depth, that is their decision; this note
does not depend on it.
