# Overnight lane A — is law missing from the search index?

**Night of 3–4 Nov 2026. Read `CLAUDE.md` first. You own `data/`, `scan/` and a NEW
`docs/DATA-GAPS.md` §19. Do not touch `core/`, `api/`, `web/`, `docs/DECISIONS.md` or any
other `DATA-GAPS` section — three other sessions are working tonight.**

## Why this exists

Reconciling Kerala on 3 Nov turned up something nobody was looking for:

- **117,119 Kerala chunks (111,804 whole cases) exist in the source parquet and are NOT in
  Qdrant** — about 4% of that court, never indexed, so unfindable by any search.
- 27,302 Qdrant chunks (9,276 cases) exist that the parquet does not have.
- Kerala's arithmetic reconciles exactly: 2,777,738 − 117,119 + 27,302 + 437,097 = 3,125,018.

**Nobody has checked whether any other court has the same hole.** If Kerala's ~4% rate holds
corpus-wide that is over a million chunks of Indian law absent from the index. For a product
promising that every claim carries a verified citation, an authority that was never indexed
cannot be retrieved, cannot be cited, and nothing in the verifier would flag it. The user gets
"not found", or a weaker authority, and no error.

**This supersedes an earlier instruction.** On 3 Nov the owner was advised NOT to resume the
full v1/v2 scan, because the v1 duplicate count changed no decision. That was right about
duplicates and wrong about coverage. The scan is back on, for this question.

## The job

1. **Resume the checkpointed v1/v2 scan**, collecting each point's `chunk_id` and `court` (and
   `court_code` where present). `acts_india` is complete; v2 had 200,000 points saved.
2. **Per court, compare distinct `chunk_id` sets** between parquet and Qdrant, as was done for
   Kerala. Table: parquet-only chunks, Qdrant-only chunks, overlap %, and whether parquet-only
   chunks cluster into whole missing cases or scatter across cases otherwise present.
3. **Whole cases missing matters far more than scattered chunks.** A missing case is invisible
   law; scattered chunks mean a case is findable but incomplete. Separate the two and say which
   dominates.
4. **Spot-check ~20 parquet-only cases.** Are they real judgments, or empty, placeholder or
   non-English rows deliberately excluded? This decides whether the gap is a defect or a filter
   working as intended.

## Timeout rule — changed for tonight

The 20-second hard stop killed this scan twice on 3 Nov, both times during disk contention.
Tonight: **60-second timeout, checkpoint every page, and on timeout back off 30 s and retry, up
to 5 consecutive failures before hard-stopping.** Abandoning a checkpointed read-only scan is
worse than retrying it. `CLAUDE.md` §9's 60 s is about service starts, not request timeouts, so
this rests on the owner's instruction, not that rule.

## Contention

Lane D runs a short Qdrant job on the copy instance tonight; both instances share one physical
disk. **Launch this as a background script and let the session exit** — a Claude session stops
working when its turn ends, so a job depending on the session staying alive will die. Write
progress and results to a file the owner can read in the morning.

## Guards

- **Read-only on the originals.** Never write to `legal_corpus_v1`, `legal_corpus_v2`,
  `acts_india` or `kanoon_v1`.
- No Voyage calls, no embedding. This job spends nothing.
- Label every figure **Measured** or **Estimate**. State "not verified" for anything not run.

## Report

Findings into the new §19, commit locally. Do not push if the rebase is not clean — say so and
leave it. End with one line: is this a coverage defect that belongs in the launch gate, or a
filter working as designed?
