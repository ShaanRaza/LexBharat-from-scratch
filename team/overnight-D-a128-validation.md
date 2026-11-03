# Overnight lane D — does A128 actually net out positive?

**Night of 3–4 Nov 2026. For the session that built A128 (commit `7abba92`) — you have the
context. Read `CLAUDE.md` and A128 first. You own `evals/`, `tests/core/` and the A128 row.
Do not touch `data/`, `docs/DATA-GAPS.md` or `docs/PRD-v2.md` — three other sessions are
working tonight.**

## Why this exists

You reported it yourself, and it is more serious than it looked: splitting dense search into
two court groups changed the top 10 by about a third — **overlap 0.68 against a single search,
with the same vector**, over 60 queries. So rank fusion over partitioned dense lists distorts
results even when there is no model benefit at all.

A128 buys about **0.56 hybrid @10 points** corpus-wide (down from 5.4 under one query model).
If the fusion distortion costs more than it gains, the config is net negative and the decision
must reopen. Right now nobody knows which way it nets.

**You said this needed a mixed-model corpus you did not have. You have one.**
`kerala_recall_eval3` is 42 off-model chunks plus 146 `voyage-4` controls — exactly that.

## The job

Run the existing recall eval on `kerala_recall_eval3` under two configurations:

- **(a)** one dense search, single `voyage-4` query vector — today's behaviour.
- **(b)** per-model partitioned dense prefetches fused by RRF, each chunk matched to its own
  model — A128 as built.

Same queries both times. Report **both query styles** (sentence-style and the paraphrase set),
dense and hybrid at @10 and @50, with cluster bootstrap CIs over targets and gained/lost
counts, exactly as the earlier swap runs did.

That isolates the net effect: model benefit minus fusion distortion, measured instead of
argued.

## How to read it

- **(b) beats (a) with the interval clear of zero** → A128 is confirmed and the row says so
  with this evidence.
- **(b) does not beat (a)** → say so plainly and **reopen A128**. The fallback to record is:
  use the per-court model only when a court filter is present, which needs one dense list and
  no fusion, and fall back to a single model otherwise. Do not implement it tonight.
- **Inconclusive** → say inconclusive. Do not round an overlapping interval into a result.

Either way, **add the distortion to A128 as a qualification** with the 0.68 overlap as the
evidence, so the row does not read as though the config is verified when its net effect is not.

## Contention and scope

Lane A is running a long background scan across both Qdrant instances tonight, and they share
one physical disk. **This job is the short one** — a small scratch collection, a few hundred
queries — so run it first and finish, rather than interleaving. Keep Voyage spend to the query
embeddings only; it should be a few rupees at most, and say what it actually cost.

## Report

Commit locally. Do not push if the rebase is not clean — say so and leave it. Label every
figure **Measured** or **Estimate**, show the test output rather than claiming it passed, and
state which of the 11 pipeline steps you touched.
