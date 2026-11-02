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
| Re-embedding the full corpus at one model | about **$1,900** at voyage-4 $0.06/M, ~31M chunks × ~1,000 tokens | **Estimate** | `DATA-GAPS.md` section 12 |
| Measuring whether that is needed | under **$1** (~420,000 Voyage tokens) | **Estimate** | the known-item run, this file section 6 |
| BM25 repair of broken sparse vectors already in the served copy | about **12 seconds** of compute, no vendor cost | **Measured** | `DATA-GAPS.md` section 9 |
| Jev credits bought so far | **$5** | **Checked** | `PRD-v2.md` section 8 |
| Tribunal data, if purchased | unknown — enquiry sent | **Needs verification** | owner, 2 Nov 2026 |

The $1,900 is the one to watch, and it is **not yet a cost** — it is the price of one option.
The measurement that decides whether it is needed costs cents. Do not treat it as committed.

---

## 3. Monthly fixed — the MVP, one server

| Item | Figure | Label |
|---|---|---|
| Server, r7g.large (ARM/Graviton) | $0.0751/hour ≈ **$55/month** at 730 hours | Their figure, **Needs verification** on the AWS calculator |
| Server, r7g.xlarge | $0.150/hour ≈ **$110/month** | Their figure, **Needs verification** |
| Managed database | — | **Quote needed** |
| S3, uploads and snapshots | — | **Quote needed** (depends on retention, `RETENTION.md`) |
| CDN | — | **Quote needed** |
| Firewall | — | **Quote needed** |
| Email | — | **Quote needed** |
| Monitoring (Langfuse, Sentry) | — | **Quote needed** |
| Secrets Manager, KMS | — | **Quote needed** |

Seven of nine lines are unquoted. That is why no total exists, and the honest thing to say to
anyone who asks is "we have the server price and nothing else."

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
| Whether the $1,900 re-embedding is needed | known-item recall@50, two query models, dense/sparse/hybrid | data session | queued, needs the Qdrant copy free |
| LLM cost per answer | token counts per pipeline step against published rates | **not assigned** | **not started** |
| Managed database, CDN, firewall, email, monitoring | quotes | owner | not started |
| Tribunal data | vendor reply | owner | enquiry sent 2 Nov 2026 |
| Final prices | deferred (O10) | owner | deferred |

---

## 7. What not to do with this file

- Do not treat section 8's worked total as a cost. It is a planning sketch with six of its
  lines estimated by us rather than quoted, and it is for internal decisions only.
- Do not quote the $1,900 as a committed cost. It is the price of one option, and the
  measurement that decides it costs under a dollar.
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
| Managed PostgreSQL, t4g.medium class | 60 | **Estimate** (ours) — no quote |
| Redis / ElastiCache, small | 20 | **Estimate** (ours) — no quote |
| S3, uploads and snapshots | 12 | **Estimate** (ours) — no quote |
| CDN | 15 | **Estimate** (ours) — no quote |
| Langfuse + Sentry | 85 | **Estimate** (ours) — no quote |
| Email (SES) | 3 | **Estimate** (ours) |
| Secrets Manager / KMS | 5 | **Estimate** (ours) |
| **Subtotal** | **~$315** | **≈ ₹26,800** |

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
| Fixed | 26,800 | 315 |
| Variable | 16,100 | 190 |
| Razorpay, ~2% + GST on ₹349,000 | 8,200 | 96 |
| **Total** | **≈ ₹51,100** | **≈ $600** |
| Revenue, 1,000 × ₹349 | 349,000 | 4,105 |
| **Gross margin** | **~85%** | |

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
about 85%. It rests on the ₹0.15 LLM estimate, so test the sensitivity: at 5× that figure,
variable cost reaches about ₹52,000 and margin still lands near 70%. It would take roughly
**20×** before ₹349 stops covering its costs. That is a wide enough margin of safety to say
the pricing hypotheses are probably sound — which is a reason to leave O10 deferred, not a
reason to settle it.

**Free users are the exposure, not paid ones.** The same 1,000 users on the free tier cost
about **₹43,000 a month and return nothing**. So the free tier's monthly limit is the most
consequential number in this model, and it is currently unset. It matters more, and sooner,
than the prices that are deferred.

### What must replace the estimates

| Line | Replaced by | Owner |
|---|---|---|
| LLM per answer | token counts per step against published rates | **unassigned** |
| Server size | Bombay sizing experiment | data session |
| Database, Redis, S3, CDN, monitoring | quotes | owner |
| Free tier limit | owner decision, informed by the above | owner |
