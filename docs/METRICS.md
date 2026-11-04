# Metrics, launch gate and validation

Targets below are **starting guesses**, to be adjusted once there is real usage. Owner for
all of them while the build is solo: **Akshita Johari (founder)**.

## Success metrics

| Metric | Starting target | Definition | How it is measured |
|---|---|---|---|
| **Verified-citation rate** | **98% or higher** | Share of authorities cited in answers that pass the verifier | Automatic run over the fixed 200-question test set, **on every release** |
| **Invented-citation rate** | **Under 0.5%** of answers | Share of answers with at least one removed citation, for any of the four citation failure reasons (`store_unavailable`, check 2 could not ask the record store, is logged separately and is not counted) | The invented-citation log, reviewed on every release |
| Answer correctness | Set from the first baseline | Each answer graded correct / partly correct / wrong | **Two advocates grade each answer blind; a third settles disagreements** |
| Verifier accuracy | Set from the first baseline | Of authorities shown as verified, the share a human confirms exists with a matching quote. **Separate from correctness** | A random sample checked by hand; sample size agreed with the advisor |
| Free to paid conversion | 3% to 5% | Paying accounts ÷ free sign-ups, counted 30 days after sign-up | Billing database |
| Answers users mark helpful | 80% or higher | Thumbs-up ÷ rated answers, plus a count of wrong-answer reports | In-app rating button |
| Gross margin per paid user | 60% or higher | (Revenue − LLM, Voyage and payment fees) ÷ revenue, per month. Fixed hosting excluded and tracked separately as monthly burn | Invoices and usage logs |
| Monthly active users | **400** at 3 months after public launch | Accounts with at least one answer in 30 days | Event log that **never stores document text** |

On the MAU target: it was lowered from 2,000 to 400 because the planned channels cannot
plausibly produce 2,000. The assumed path to ~400 counts every sign-up as still active,
which no product achieves; at 60% month-on-month retention the same inputs give about 250.
Set the real number after the beta.

## The 200-question test set

Frozen so results can be compared release to release. **The advocate advisor signs it off
before it is used.**

| Part | Count |
|---|---|
| Real questions collected in the validation interviews | 100 |
| Act and section lookups | 50 |
| **Traps** — cases that do not exist, wrong section numbers, events after the snapshot date | **50** |

This mix is a proposal (Estimate). The traps are what prove the verifier and the
out-of-scope detection actually work; do not drop them to raise the score.

See [TESTING.md](TESTING.md) for how it runs.

## Launch gate

Public launch (months 4 to 5) happens only if **all** of these are true at the end of the
private beta (weeks 11 to 14):

- [ ] a. Verified-citation rate **98% or higher** on the 200-question test set
- [ ] b. At least **6 of the 10** beta advocates say they would pay the proposed Pro price
- [ ] c. **Zero** confirmed fabricated citations reaching a beta user, **and** fewer than
      0.5% of test-set answers have a removed citation
- [ ] d. The advocate's **written legal opinion** received
- [ ] e. Voyage's **written no-training and retention terms** received
- [ ] f. The **independent security test** passed
- [ ] g. The **data-as-of date shown prominently** on every result, stats page and Act page

**If any condition fails, the launch date moves. Akshita Johari decides.**

> **Note on condition (g).** The PRD's seventh condition was "the first data refresh is
> complete and reconciled". Tech Stack decisions **D2 and D5** moved the refresh pipeline to
> the post-MVP backlog and replaced that condition with the data-as-of date. The Tech Stack
> wins, so (g) above is the operative condition — but the PRD still reads the old way.

## User validation plan

**This PRD is entirely assumption-based. No lawyer has been interviewed.** Before any code
beyond the audit spike, run about **20 interviews of 30–45 minutes**:

| Group | Count |
|---|---|
| District court advocates | 8 |
| High Court advocates | 6 |
| Law students | 6 |

Recruit through own contacts, the law-school pilots, bar association introductions and
LinkedIn. Everyone interviewed gets free access.

### Assumptions being tested

| Assumption | How it is tested | A result that would change the roadmap |
|---|---|---|
| Advocates trust an answer with a "record found" badge | Show 10 sample answers; ask what they would still check | If most re-check every citation elsewhere, the badge will not sell the product — invest in one-click source viewing instead |
| Outcome statistics are wanted | Show a mock statistics page; ask what decision it would inform | If few would use it, drop it from the headline features and the free-tier wedge |
| ₹199 and ₹499 are right | Ask price questions at several price points | Follow the evidence table in [PRODUCT.md](PRODUCT.md) |
| Lawyers work from phones | Ask which device and network; watch one real research session | If most use desktops, cut the mobile budget |
| Hindi is needed | Ask which language they research in | If strongly needed, move Hindi from P1 to P0 |
| Statute lookup + SC precedent + drafting is enough for district-court advocates | Ask directly; watch one real session | If not, move the High Court phase 2 earlier, or stop treating district-court advocates as a launch target |
| Advocates will upload client documents | Ask how they feel about privilege and confidentiality | If few would, revisit the upload limits and the warning wording |
| Free tools such as Indian Kanoon are enough | Ask what they use now and what frustrates them | If they are satisfied, focus on students first |

The interviews also settle **which High Courts come first in phase 2**.

## Retention

Track week-4 retention of free users, month-3 retention of paying users, and monthly churn.
**No target is set** — none has been measured. Set it after the beta from the break-even in
the channel economics: paying users must stay long enough for their gross profit to cover
the cost of acquiring them.

Revenue a paying user brings, before model, hosting and payment costs:

| Months as a paying user | Student (₹199) | Pro (₹499) |
|---|---|---|
| 3 | ₹597 | ₹1,497 |
| 6 | ₹1,194 | ₹2,994 |
| 12 | ₹2,388 | ₹5,988 |

Scale a paid channel only when its measured acquisition cost is well below the gross profit
a user brings before churning.

<!-- latency-before:begin -->
## Latency against the CLAUDE.md section 10 targets, BEFORE the `chunk_id` index (measured 4 Nov 2026)

**Conditions.** Measured 4 Nov 2026, 100 questions run one at a time by `evals/performance/measure.py` (timings captured in the runner; Langfuse is not involved). **Instance check before starting:** six samples, Qdrant on port 7333 at 0.0% CPU, no other client on the port, machine load 4.6 to 5.2. **During the run (2,165 samples, every 2 s):** no other client was ever on the port (0 contended questions, nothing re-run), Qdrant CPU peaked at 400% (our own hybrid queries; it is not used as a contention signal, see `evals/performance/timing.py`), machine load peaked at 8.5 on 10 cores. Another session's `scan/sc/measure_refs.py` was using about one core throughout; it holds no connection to the Qdrant port. **Setup, which flatters some numbers and not others:** Qdrant is the local copy (`kanoon_v1`, 455,755 points, on this machine, so no network hop); `act_id` is payload-indexed, `chunk_id` and `case_number` are not; Jev is off, so Gemini makes every decision (`gemini-3.5-flash-lite` for rewrite, scope and gate); the cache and the store are in-memory stand-ins, so steps 4 and 11 carry no Redis or Postgres hop; step 10 (Show) streams after step 11 as the API bridge runs it, so first word equals the end of step 11 plus the first word of Show (about 0 ms here). The rate limiter was off (0 rate-limit hits, 29 s of back-off in all, 1 non-rate-limit model error, handled by the fallback). **Cost:** 1,555 Gemini calls (1,226,968 tokens in, 51,087 out), 100 Voyage embeddings and 99 re-ranks; the repo records no Gemini or Voyage prices (`AI_PRICE_*` unset), so the cost is stated in calls and tokens, not dollars. **Outcomes:** 89 answered, 10 `not_found`, 1 out of scope; the two answer targets are measured on the 89 answered. Nothing was optimised.

A target PASSES when its p95 is under it. p50 and p95 are percentiles of the recorded times, never averages.

| Measure | Target | p50 | p95 | n | Result |
|---|---|---:|---:|---:|---|
| First word of a research answer | under 3 s | 38.7 s | 117.4 s | 89 | **FAIL** |
| Full research answer | under 20 s | 38.7 s | 117.4 s | 89 | **FAIL** |
| Search stage (search + re-rank) | under 800 ms | 799 ms | 2,110 ms | 99 | **FAIL** |
| Each Gemini decision: scope decision | under 800 ms | 1,224 ms | 1,626 ms | 100 | **FAIL** |
| Each Gemini decision: gate rating (one passage) | under 800 ms | 1,229 ms | 1,622 ms | 691 | **FAIL** |
| Each Gemini decision: claim check (verifier check 4) | under 800 ms | 992 ms | 1,619 ms | 574 | **FAIL** |
| Act / section lookup (search step, exact or Act-scoped) | under 500 ms | 9 ms | 38 ms | 57 | PASS |

### Per step (the 11 pipeline steps)

| Step | p50 | p95 | n | Median spent inside vendor calls |
|---|---:|---:|---:|---|
| 1 Remember | 0 ms | 0 ms | 100 | none (our own code) |
| 2 Rewrite | 1.2 s | 1.9 s | 100 | gemini 1.2 s |
| 3 Decide (scope check, in parallel with the query embedding) | 1.2 s | 1.7 s | 100 | decision 1.2 s, gemini 1.2 s, voyage 1.0 s |
| 4 Cache (in-memory stand-in) | 0 ms | 0 ms | 99 | none (our own code) |
| 5 Search | 25 ms | 155 ms | 99 | qdrant 24 ms |
| 6 Re-rank | 723 ms | 1.9 s | 99 | voyage 723 ms |
| 7 Gate | 1.5 s | 1.8 s | 99 | decision 1.5 s, gemini 1.5 s |
| 8 Answer | 1.8 s | 3.2 s | 90 | gemini 1.8 s |
| 9 Verify | 31.8 s | 109.2 s | 90 | qdrant 26.9 s, decision 5.3 s, gemini 5.3 s |
| 10 Show (after step 11, as the API bridge runs it) | 0 ms | 0 ms | 100 | none (our own code) |
| 11 Save (in-memory stand-in) | 0 ms | 0 ms | 100 | none (our own code) |

### Where the time goes, for each failure

- **First word of a research answer** (p95 117.4 s against 3.0 s): 9 Verify p50 31.8 s (median inside: qdrant 26.9 s, decision 5.3 s, gemini 5.3 s); 8 Answer p50 1.8 s (median inside: gemini 1.8 s); 7 Gate p50 1.5 s (median inside: decision 1.5 s, gemini 1.5 s); with step 9 taken out the same questions would be p50 7.0 s, p95 9.0 s.
- **Full research answer** (p95 117.4 s against 20.0 s): 9 Verify p50 31.8 s (median inside: qdrant 26.9 s, decision 5.3 s, gemini 5.3 s); 8 Answer p50 1.8 s (median inside: gemini 1.8 s); 7 Gate p50 1.5 s (median inside: decision 1.5 s, gemini 1.5 s); with step 9 taken out the same questions would be p50 7.0 s, p95 9.0 s.
- **Search stage (search + re-rank)** (p95 2.1 s against 800 ms): search (Qdrant) p50 25 ms, p95 155 ms; re-rank (Voyage) p50 723 ms, p95 1.9 s.
- **Each Gemini decision: scope decision** (p95 1.6 s against 800 ms): the whole decision p50 1.2 s, p95 1.6 s, of which the Gemini API call p50 1.2 s, p95 1.6 s (our own code adds the difference).
- **Each Gemini decision: gate rating (one passage)** (p95 1.6 s against 800 ms): the whole decision p50 1.2 s, p95 1.6 s, of which the Gemini API call p50 1.2 s, p95 1.6 s (our own code adds the difference).
- **Each Gemini decision: claim check (verifier check 4)** (p95 1.6 s against 800 ms): the whole call p50 992 ms, p95 1.6 s; claim_support is not timed separately inside the API call, so the call time is the Gemini round trip plus our parsing.

### Other measured calls (for reading the table, not targets)

| Call | p50 | p95 | n |
|---|---:|---:|---:|
| decision:claim_support | 992 ms | 1.6 s | 574 |
| decision:decide | 1.2 s | 1.6 s | 100 |
| decision:rate_passage | 1.2 s | 1.6 s | 691 |
| gemini:decide | 1.2 s | 1.6 s | 100 |
| gemini:rate_passage | 1.2 s | 1.6 s | 691 |
| gemini:rewrite | 1.2 s | 1.9 s | 100 |
| gemini:text | 1.0 s | 2.1 s | 665 |
| qdrant:exact | 8 ms | 35 ms | 80 |
| qdrant:get_record | 5.4 s | 5.8 s | 574 |
| qdrant:hybrid | 111 ms | 172 ms | 55 |
| voyage:embed | 1.1 s | 1.4 s | 100 |
| voyage:rerank | 723 ms | 1.9 s | 99 |

<!-- latency-before:end -->

<!-- latency:begin -->
## Latency against the CLAUDE.md section 10 targets (measured 4 to 5 Nov 2026, after the chunk_id index)

**Conditions.** Measured 4 to 5 Nov 2026 (started 23:15 IST), the same 100 questions, one at a time, by `evals/performance/measure.py`, after `chunk_id` was payload-indexed on `kanoon_v1` (DECISIONS A150). Same setup as the block above: local copy instance (455,755 points), `act_id` and `chunk_id` indexed, `case_number` not, Jev off so Gemini decides (`gemini-3.5-flash-lite`), in-memory cache and store stand-ins, Show after Save, limiter off. **Instance check before starting:** six samples, Qdrant at 0.0% CPU, no other client on the port, machine load 8.0. **Contention, in full:** the first 87 questions ran with no other client on the port. From question 83 another session's job put eight clients on port 7333 (Qdrant CPU peaked at 762%, machine load at 24.7); the harness flagged 13 questions (q083 to q098) as contended, waited for the instance to go quiet, and re-ran them; nothing contended is reported (`unresolved_contended` is empty). Another session's `scan/sc/measure_refs.py` used about one core throughout and holds no connection to the port. **Cost:** 1,780 Gemini calls (1,457,765 tokens in, 59,437 out), 100 Voyage embeddings and 98 re-ranks, 0 rate-limit hits, 1 non-rate-limit model error (handled by the fallback); no prices are recorded in the repo, so no dollars. **Outcomes:** 88 answered, 10 `not_found`, 2 out of scope; the two answer targets are measured on the 88 answered. Nothing was optimised.

**Before and after the `chunk_id` index** (the same 100 questions; before = block below this one):

| Measure | Before | After |
|---|---:|---:|
| Step 9 Verify p50 / p95 | 31.8 s / 109.2 s | 4.1 s / 14.1 s |
| Qdrant inside Verify, median | 26.9 s | 18 ms |
| Qdrant `get_record` per call, p50 / p95 | 5.4 s / 5.8 s | 4 ms / 12 ms (521 calls) |
| First word = full answer, p50 / p95 | 38.7 s / 117.4 s | 10.7 s / 22.0 s |
| Before the answer step starts, p50 / p95 | 5.0 s / 6.6 s | 4.7 s / 5.8 s |
| First word with Verify taken out, p50 / p95 | 7.0 s / 9.0 s | 6.4 s / 8.5 s |

Step 10 (Show) waits for steps 9 and 11, so first word equals full answer (DECISIONS, the open Step 10 row). The Voyage re-rank moved from p50 0.72 s to 0.87 s between the two runs with no change on our side, which is the run-to-run drift to expect from a vendor call.

A target PASSES when its p95 is under it. p50 and p95 are percentiles of the recorded times, never averages.

| Measure | Target | p50 | p95 | n | Result |
|---|---|---:|---:|---:|---|
| First word of a research answer | under 3 s | 10.7 s | 22.0 s | 88 | **FAIL** |
| Full research answer | under 20 s | 10.7 s | 22.0 s | 88 | **FAIL** |
| Search stage (search + re-rank) | under 800 ms | 986 ms | 1,922 ms | 98 | **FAIL** |
| Each Gemini decision: scope decision | under 800 ms | 1,162 ms | 1,558 ms | 100 | **FAIL** |
| Each Gemini decision: gate rating (one passage) | under 800 ms | 1,039 ms | 1,443 ms | 676 | **FAIL** |
| Each Gemini decision: claim check (verifier check 4) | under 800 ms | 915 ms | 1,227 ms | 517 | **FAIL** |
| Act / section lookup (search step, exact or Act-scoped) | under 500 ms | 12 ms | 61 ms | 56 | PASS |

### Per step (the 11 pipeline steps)

| Step | p50 | p95 | n | Median spent inside vendor calls |
|---|---:|---:|---:|---|
| 1 Remember | 0 ms | 0 ms | 100 | none (our own code) |
| 2 Rewrite | 1.1 s | 1.4 s | 100 | gemini 1.1 s |
| 3 Decide (scope check, in parallel with the query embedding) | 1.2 s | 1.6 s | 100 | decision 1.2 s, gemini 1.2 s, voyage 1.0 s |
| 4 Cache (in-memory stand-in) | 0 ms | 0 ms | 98 | none (our own code) |
| 5 Search | 43 ms | 233 ms | 98 | qdrant 41 ms |
| 6 Re-rank | 872 ms | 1.8 s | 98 | voyage 872 ms |
| 7 Gate | 1.3 s | 1.8 s | 98 | decision 1.3 s, gemini 1.3 s |
| 8 Answer | 1.6 s | 3.0 s | 89 | gemini 1.6 s |
| 9 Verify | 4.1 s | 14.1 s | 89 | decision 4.1 s, gemini 4.1 s, qdrant 18 ms |
| 10 Show (after step 11, as the API bridge runs it) | 0 ms | 0 ms | 100 | none (our own code) |
| 11 Save (in-memory stand-in) | 0 ms | 0 ms | 100 | none (our own code) |

### Where the time goes, for each failure

- **First word of a research answer** (p95 22.0 s against 3.0 s): 9 Verify p50 4.1 s (median inside: decision 4.1 s, gemini 4.1 s, qdrant 18 ms); 8 Answer p50 1.6 s (median inside: gemini 1.6 s); 7 Gate p50 1.3 s (median inside: decision 1.3 s, gemini 1.3 s); with step 9 taken out the same questions would be p50 6.4 s, p95 8.5 s.
- **Full research answer** (p95 22.0 s against 20.0 s): 9 Verify p50 4.1 s (median inside: decision 4.1 s, gemini 4.1 s, qdrant 18 ms); 8 Answer p50 1.6 s (median inside: gemini 1.6 s); 7 Gate p50 1.3 s (median inside: decision 1.3 s, gemini 1.3 s); with step 9 taken out the same questions would be p50 6.4 s, p95 8.5 s.
- **Search stage (search + re-rank)** (p95 1.9 s against 800 ms): search (Qdrant) p50 43 ms, p95 233 ms; re-rank (Voyage) p50 872 ms, p95 1.8 s.
- **Each Gemini decision: scope decision** (p95 1.6 s against 800 ms): the whole decision p50 1.2 s, p95 1.6 s, of which the Gemini API call p50 1.2 s, p95 1.6 s (our own code adds the difference).
- **Each Gemini decision: gate rating (one passage)** (p95 1.4 s against 800 ms): the whole decision p50 1.0 s, p95 1.4 s, of which the Gemini API call p50 1.0 s, p95 1.4 s (our own code adds the difference).
- **Each Gemini decision: claim check (verifier check 4)** (p95 1.2 s against 800 ms): the whole call p50 915 ms, p95 1.2 s; claim_support is not timed separately inside the API call, so the call time is the Gemini round trip plus our parsing.

### Other measured calls (for reading the table, not targets)

| Call | p50 | p95 | n |
|---|---:|---:|---:|
| decision:claim_support | 915 ms | 1.2 s | 517 |
| decision:decide | 1.2 s | 1.6 s | 100 |
| decision:rate_passage | 1.0 s | 1.4 s | 676 |
| gemini:decide | 1.2 s | 1.6 s | 100 |
| gemini:rate_passage | 1.0 s | 1.4 s | 677 |
| gemini:rewrite | 1.1 s | 1.4 s | 100 |
| gemini:text | 947 ms | 1.9 s | 606 |
| qdrant:exact | 11 ms | 52 ms | 77 |
| qdrant:get_record | 4 ms | 12 ms | 521 |
| qdrant:hybrid | 126 ms | 252 ms | 52 |
| voyage:embed | 1.0 s | 1.2 s | 100 |
| voyage:rerank | 872 ms | 1.8 s | 98 |

<!-- latency:end -->
