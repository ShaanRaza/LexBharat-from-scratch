# Overnight lane A — is law missing from the search index?

**Night of 3–4 Nov 2026. Read `CLAUDE.md` first. You own `data/`, `scan/` and
`docs/DATA-GAPS.md` §19 for this job. Do not touch `core/`, `api/`, `web/` or any other
`DATA-GAPS` section — three other sessions are working tonight.**

## Why this exists

Reconciling Kerala on 3 Nov turned up something nobody was looking for:

- **117,119 Kerala chunks (111,804 whole cases) exist in the source parquet and are NOT in
  Qdrant.** About 4% of that court, never indexed, so unfindable by any search.
- 27,302 Qdrant chunks (9,276 cases) exist that the parquet does not have.
- Kerala's arithmetic reconciles exactly: 2,777,738 − 117,119 + 27,302 + 437,097 = 3,125,018.

**Nobody has checked whether any other court has the same hole.** If Kerala's ~4% rate holds
corpus-wide that is over a million chunks of Indian law absent from the index. For a product
whose promise is that every claim carries a verified citation, an authority that was never
indexed cannot be retrieved, cannot be cited, and nothing in the verifier would ever flag it.
The user gets "not found", or a weaker authority, and no error.

**This supersedes an earlier instruction.** On 3 Nov the owner was advised NOT to resume the
full v1/v2 scan, on the grounds that the v1 duplicate count changed no decision. That was
right about duplicates and wrong about coverage. The scan is back on, for this question.

## The job

1. **Resume the checkpointed v1/v2 scan**, collecting each point's `chunk_id` and `court`
   (and `court_code` where present). `acts_india` is already complete; v2 had 200,000 points
   saved before it stopped.
2. **Per court, compare distinct `chunk_id` sets** between the parquet and Qdrant, exactly as
   was done for Kerala. Report, as a table: parquet-only chunks, Qdrant-only chunks, the
   overlap percentage, and whether parquet-only chunks cluster into whole missing cases or
   scatter across cases that are otherwise present.
3. **Whole cases missing matters far more than scattered chunks.** A case missing entirely is
   invisible law. Scattered chunks mean a case is findable but incomplete. Separate the two in
   the table and say which dominates.
4. **Spot-check what the parquet-only cases actually are.** Read ~20 of them. Are they real
   judgments, or empty/placeholder/non-English rows that were deliberately excluded? This
   decides whether the gap is a defect or a filter working as intended.

## Timeout rule — changed for tonight

The 20-second hard stop killed this scan twice on 3 Nov, both times during disk contention.
Tonight: **60-second timeout, checkpoint every page, and on timeout back off 30 s and retry,
up to 5 consecutive failures before hard-stopping.** Abandoning a checkpointed read-only scan
is worse than retrying it. `CLAUDE.md` §9's 60 s is about service starts, not request
timeouts, so this rests on the owner's instruction, not on that rule.

## Contention

Another session (lane D) is running a short Qdrant job on the copy instance tonight. Both
instances share one physical disk. **Launch this as a background script and let the session
exit** — a Claude session stops working when its turn ends, so a job that depends on the
session staying alive will die. Write progress and results to a file the owner can read in the
morning.

## Guards

- **Read-only on the originals.** Never write to `legal_corpus_v1`, `legal_corpus_v2`,
  `acts_india` or `kanoon_v1`.
- No Voyage calls. No embedding. This job spends nothing.
- State "not verified" for anything not actually run.

## Report

Write findings into a NEW `docs/DATA-GAPS.md` §19 so you do not collide with other sessions'
edits, label every figure **Measured** or **Estimate**, and commit locally. Do not push if the
rebase is not clean — say so and leave it. Then state in one line whether this is a coverage
defect that belongs in the launch gate, or a filter working as designed.
