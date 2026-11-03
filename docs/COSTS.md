# What this costs to run

**Do not quote a monthly total to anyone yet.** `TECH-STACK-v2.md` section 9 retired the
original ₹7,200–7,500 figure when the topology changed, and nothing has replaced it. This
file is the structure that will replace it: every line item, the ones that are known filled
in with their original evidence labels, and the unknowns named with what settles each.

Evidence labels follow `CLAUDE.md` section 9.5: **Measured**, **Checked**, **Estimate**,
**Needs verification**. Nothing here is promoted without measuring it.

---

## 1. Three cost drivers, and they scale differently

This is the part that matters for planning, and it is why a single "cost per user" is
misleading.

| Driver | Grows with | Shape |
|---|---|---|
| **Corpus size** — Qdrant memory and disk | how much data is served, **not** how many users | Step change, then flat |
| **Answers** — Voyage, Jev, LLM calls | number of answers written | Linear |
| **Uploads** — OCR, S3, worker time | paid users who upload | Linear, lumpy |

The consequence: **at low user counts almost all of the bill is the corpus**, which does not
care whether anyone is logged in. The first hundred users are extraordinarily expensive per
user, and the single biggest lever on monthly burn is how much of the corpus is served — not
pricing, not usage limits.

That also means the corpus decision and the pricing decision are independent. Deferring
pricing (O10) costs nothing. Deferring the corpus decision costs the difference between one
server and several, every month, forever.

---

## 2. One-off costs

| Item | Figure | Label | Source |
|---|---|---|---|
| Re-embedding, if needed at all | **$0** for a per-court config (~92% matched); else ~$560 at `voyage-4-lite`, ~$1,700 at `voyage-4`, **~$3,400 at `voyage-4-large`** (what `kanoon_v1` serves) | **Measured** (28B tokens) | `DATA-GAPS.md` section 13 |
| Measuring whether that is needed | under **$1** (~420,000 Voyage tokens) | **Estimate** | the known-item run, this file section 6 |
| BM25 repair of broken sparse vectors already in the served copy | about **12 seconds** of compute, no vendor cost | **Measured** | `DATA-GAPS.md` section 9 |
| Jev credits bought so far | **$5** | **Checked** | `PRD-v2.md` section 8 |
| Tribunal data, if purchased | unknown — enquiry sent | **Needs verification** | owner, 2 Nov 2026 |
| **Re-embedding Kerala's dead vectors** | about **$12** at `voyage-4` (~215,000 chunks, ~194M tokens); detection costs **nothing** — one dot product per point | **Measured** | `DATA-GAPS.md` section 14 |

**Measured 2 Nov 2026: the working answer is $0.** A per-court-majority query config matches
about 92% of High Court points, Qdrant serves it in one call for about 1.8 ms more, and hybrid
search loses nothing measurable to a mismatched query. Re-embedding is now a quality choice
rather than a necessity — and matching the model `kanoon_v1` already serves would cost about
**$3,400**, not the $1,900 once assumed. Details: `DATA-GAPS.md` section 13.

---

## 2b. All vector work, consolidated

Every embedding and vector cost measured as of 3 Nov 2026. Sources: `DATA-GAPS.md` sections 9,
13 and 14.

| Work | Vendor spend | Note |
|---|---:|---|
| All measurement to date | **~$0.20** | ~3M Voyage tokens, inside the free allowance |
| ~~BM25 repair, 19,835 Central Act points in `kanoon_v1`~~ | **$0 — ALREADY DONE** | Applied earlier with a verified backup, dense vectors untouched; re-checked read-only 3 Nov 2026, 0 of 74,484 Central points would change. The copy is **not** serving broken keyword vectors. The 19,835 are still broken in the original `acts_india` and matter only when those are copied |
| BM25 repair, ~504,600 remaining Act points | **$0** | Same, local; write speed at that scale untested |
| Kerala dead-vector **detection**, all 3.1M | **$0** | One dot product per point, no vendor calls (§14) |
| Kerala dead-vector **re-embed**, **217,766 chunks (measured, not estimated)** | **~$11.8** | ~196M tokens at `voyage-4`, Kerala's majority model. Count, threshold and precision all validated — `DATA-GAPS.md` §16 |
| The 10,112 missing Supreme Court chunks | **~$0.61** | ~10M tokens |
| Per-court query models for High Courts | **$0** | Config plus ~1.8 ms latency — this replaced the $1,900 |
| Serving the three High Courts | **$0** | Already embedded in `legal_corpus_v1`/`v2`; only the local copy costs anything |
| **Total one-off to a clean corpus** | **≈ $13** | |

Not taken, for contrast: full re-embedding is $560 (`voyage-4-lite`), $1,700 (`voyage-4`) or
**$3,400** (`voyage-4-large`) — and $3,400 is the honest figure for that path, being the model
`kanoon_v1` already serves.

Ongoing after all of it: **₹0.05 per answer** for query embedding (section 4).

**The whole $13 is gated by one thing.** At the throttled free tier (10,000 tokens a minute) the
Kerala job alone is about 13 days and the Supreme Court job about 17 hours. With the payment
method live, both finish inside an hour. This is the clearest case in the project of a trivial
cost blocking real work.

---

## 3. Monthly fixed — the MVP, one server

| Item | Figure | Label |
|---|---|---|
| Server, r7g.large (ARM/Graviton) | $0.0751/hour ≈ **$55/month** at 730 hours | Their figure, **Needs verification** on the AWS calculator |
| Server, r7g.xlarge | $0.150/hour ≈ **$110/month** | Their figure, **Needs verification** |
| Managed PostgreSQL, db.t4g.medium, Mumbai | **$61/mo** on demand; $45 on a 1-year reservation, $36 on 3-year | **List price** (aggregator), compute only |
| S3, uploads and snapshots | ~$0.025 per GB per month, Mumbai | **Estimate** from list price |
| CDN (CloudFront) | ~$10–20/mo at launch traffic | **Estimate** |
| Firewall | security groups free; AWS WAF from ~$5/mo plus per-rule charges | **Estimate** |
| Email (SES) | ~$1–5/mo at launch volume | **Estimate** |
| Langfuse | **free** to 50,000 units/mo, then **$29/mo** (Core), $8 per 100k overage | **List price** (aggregator) |
| Sentry | **free** to 5,000 errors/mo, then **$29/mo** (Team) | **List price** (aggregator) |
| Secrets Manager, KMS | ~$0.40 per secret per month | **Estimate** from list price |
| Redis | **$0** co-hosted on the app server; ~$20/mo managed | **Estimate** |

These are **published list prices, fetched 2 Nov 2026, not quotes** — and the database and
monitoring figures came from third-party aggregators rather than the vendors. A real quote
means the AWS calculator against a chosen configuration in ap-south-1, which needs the server
size the sizing experiment has not returned.

Three things the fetch changed. The database figure is compute only — storage, IOPS, backups
and transfer are billed on top, and a one-year reservation cuts it about a quarter. **Both
monitoring tools are free at launch volumes**, so that line is $0 until traffic passes
Langfuse's 50,000 units and Sentry's 5,000 errors a month. And Redis needs no managed instance
at this size.

Sources: [RDS db.t4g.medium](https://www.bytebase.com/dbcost/rds/instance/db.t4g.medium.md) ·
[Langfuse](https://costbench.com/software/ai-observability/langfuse/) ·
[Sentry](https://costbench.com/software/developer-tools/sentry). Server hourly prices are
carried from the original PRD and Tech Stack and are still unchecked against AWS.

**Qdrant Cloud versus self-hosted is not in this table yet** because the Bombay sizing
experiment has not reported. That experiment measures resident memory and search latency for
three quantization settings and extrapolates to the full corpus; until it does, the server
size is a guess and a managed-service quote cannot be compared against anything.

---

## 4. Variable — per answer

| Component | Figure | Label |
|---|---|---|
| Voyage (embedding the query) | about **₹0.05** per answer | **Estimate** |
| Jev (decide, gate, claim support) | about **₹0.03** per answer | **Estimate** |
| LLM calls (rewrite, answer) | **2–3 calls, unpriced** | **Not known** |
| Verifier checks 1–3 | **free** — plain Python | **Checked** |
| Act and section lookup | **free** — payload filter, no embedding | **Checked** |
| Cache hit | **free**, and does not count against the user's limit | **Checked** |

**The per-answer cost is not known**, because the largest component of it — the LLM calls —
has no price against it anywhere in the docs. Everything downstream of that number is
therefore also unknown:

- whether the ₹499 hypothesis clears its costs at any particular usage limit
- the 60% gross-margin target in `METRICS.md`, which cannot currently be checked against
  anything
- what the free tier's monthly limit should be

Pricing them is a half-hour job — model name, token counts per step, published rate — and it
unblocks all three. It is the cheapest high-value measurement outstanding.

---

## 5. What changes at scale

Two different kinds of growth, often confused:

**Corpus growth (serving more data).** Step change in Qdrant memory, disk and therefore
server size. Possibly a one-off re-embedding. **No change at all** to per-answer cost. A
corpus several times larger is a bigger monthly bill whether it serves ten users or ten
thousand.

**User growth (more answers).** Linear in Voyage + Jev + LLM. Cache hits blunt it, and the
cache is free. Qdrant search cost per query barely moves until concurrency forces a second
server. Uploads are the lumpy part: OCR on scanned documents is the most expensive per-unit
operation in the system, and `CLAUDE.md` section 10 already flags OCR time and Qdrant memory
as the two things expected to break first on a 16 GB server.

The practical reading: **the corpus decision sets the floor, user growth sets the slope, and
uploads set the risk.** Watch Qdrant memory and OCR time in Langfuse from week one.

---

## 6. Open inputs — what settles each

| Unknown | What settles it | Owner | Status |
|---|---|---|---|
| Server size and whether managed Qdrant is worth it | Bombay sizing experiment — RAM, p50/p95, recall@10/@50 for three quantization settings, extrapolated | data session | running, 2 Nov 2026 |
| ~~Whether the $1,900 re-embedding is needed~~ | **Measured 2 Nov 2026 — per-court config, $0** | data session | done (`DATA-GAPS.md` §13) |
| ~~Whether any dense vectors are unrelated to their text~~ | **Measured 3 Nov 2026 — 6.9% of Kerala v2, nowhere else; sparse intact so hybrid still finds them** | data session | done (`DATA-GAPS.md` §14) |
| Finding the remaining ~215,000 dead Kerala vectors | the free detector: score every vector against the mean legal-text direction, validate the threshold on the 31 known-dead and 419 known-good | data session | **not started — costs nothing to run** |
| Re-embedding what it flags | **blocked on the payment method, not on engineering** — $12 of tokens, but 13 days at the throttled free tier | owner | **one card activation** |
| LLM cost per answer | token counts per pipeline step against published rates | **not assigned** | **not started** |
| Managed database, CDN, firewall, email, monitoring | quotes | owner | not started |
| Tribunal data | vendor reply | owner | enquiry sent 2 Nov 2026 |
| Final prices | deferred (O10) | owner | deferred |

---

## 7. What not to do with this file

- Do not treat section 8's worked total as a cost. It is a planning sketch with six of its
  lines estimated by us rather than quoted, and it is for internal decisions only.
- Do not quote $1,900 at all any more. It was superseded on 2 Nov 2026: the working answer is
  $0 for a per-court query config, and full re-embedding costs $560 to $3,400 depending on the
  model chosen (`DATA-GAPS.md` section 13).
- Do not promote an **Estimate** to a figure without measuring it (`CLAUDE.md` section 9.5).
- Prices charged to users are the owner's decision (O10, `CLAUDE.md` section 8). This file
  records what things cost us, never what anyone is charged.

---

## 8. A worked total — complete product, 1,000 paying users

**This is a planning sketch, not a quote.** Section 7's rule stands: do not give this number
to anyone outside. Six of its lines are my own estimates from standard cloud pricing, not
quotes we hold. It exists so the server and corpus decisions can be made against *something*
rather than nothing, and every line is labelled so the sketch can be replaced piece by piece
as real quotes arrive.

**Assumptions** — change any of these and the total moves:

- ₹85 to the dollar (approximate)
- "Complete product" = the v1 scope including the three High Courts named in `CLAUDE.md` §1
- 1,000 paying users at the blended **₹349** from `PRODUCT.md` (half Student, half Pro)
- 100 answers per user per month
- 30% cache hit rate, so 70,000 billable answers

### Fixed monthly

| Line | $/mo | Basis |
|---|---:|---|
| Server r7g.xlarge (4 vCPU / 32 GB, ARM) | 110 | Their hourly figure, **Needs verification** |
| EBS gp3, ~60 GB | 5 | **Estimate** (ours) |
| Managed PostgreSQL, db.t4g.medium, Mumbai | 61 | **List price** |
| Redis, co-hosted on the app server | 0 | **Estimate** (ours) |
| S3, uploads and snapshots | 12 | **Estimate** (ours) |
| CDN | 15 | **Estimate** (ours) |
| Langfuse Core plus overage at this volume | 61 | **List price** + our usage estimate |
| Sentry Team | 29 | **List price** |
| Email (SES) | 3 | **Estimate** (ours) |
| Secrets Manager / KMS | 5 | **Estimate** (ours) |
| **Subtotal** | **~$301** | **≈ ₹25,600** |

### Variable, at 70,000 billable answers

| Component | Per answer | Monthly |
|---|---:|---:|
| Voyage, query embedding | ₹0.05 (**Estimate**) | ₹3,500 |
| Jev — decide, gate, claim support | ₹0.03 (**Estimate**) | ₹2,100 |
| LLM calls — rewrite and answer | **~₹0.15 (Estimate, ours — the weakest number here)** | ₹10,500 |
| Verifier checks 1–3, Act lookup, cache hits | free (**Checked**) | — |
| **Subtotal** | **~₹0.23** | **≈ ₹16,100** |

### Total

| | ₹/mo | $/mo |
|---|---:|---:|
| Fixed | 25,600 | 301 |
| Variable | 16,100 | 190 |
| Razorpay, ~2% + GST on ₹349,000 | 8,200 | 96 |
| **Total** | **≈ ₹49,900** | **≈ $587** |
| Revenue, 1,000 × ₹349 | 349,000 | 4,105 |
| **Gross margin** | **~86%** | |

The list prices fetched on 2 Nov 2026 moved this total about 2% against the first sketch, so
the estimates were close and the shape of the answer does not depend on them. Langfuse is the
one line that grows awkwardly: its included 100,000 units are exceeded at this volume and
overage runs $8 per 100,000.

### Server scenarios — the line that actually moves

| Corpus | Est. RAM at int8 | Instance | $/mo |
|---|---:|---|---:|
| Launch corpus only (~446k points) | under 1 GB | r7g.large | 55 |
| Complete product, three High Courts | ~5–12 GB | r7g.xlarge | 110 |
| Full corpus (32.5M points) | **~45–55 GB** | r7g.2xlarge | 219 + ~$28 disk |

Those RAM figures are arithmetic, **not measured**: 1024-dimension vectors at int8 are roughly
1 KB per point in memory, plus the HNSW graph. The Bombay sizing experiment measures this
directly and its result replaces this table.

### What this tells us

**The margin target is not at risk.** `METRICS.md` wants 60% or better; this sketch gives
about 86%. It rests on the ₹0.15 LLM estimate, so test the sensitivity: at 5× that figure,
variable cost reaches about ₹52,000 and margin still lands near 70%. It would take roughly
**20×** before ₹349 stops covering its costs. That is a wide enough margin of safety to say
the pricing hypotheses are probably sound — which is a reason to leave O10 deferred, not a
reason to settle it.

**Free users are the exposure, not paid ones.** The same 1,000 users on the free tier cost
about **₹41,000 a month and return nothing**. So the free tier's monthly limit is the most
consequential number in this model, and it is currently unset. It matters more, and sooner,
than the prices that are deferred.

### What must replace the estimates

| Line | Replaced by | Owner |
|---|---|---|
| LLM per answer | token counts per step against published rates | **unassigned** |
| Server size | Bombay sizing experiment | data session |
| Database, Redis, S3, CDN, monitoring | quotes | owner |
| Free tier limit | owner decision, informed by the above | owner |
