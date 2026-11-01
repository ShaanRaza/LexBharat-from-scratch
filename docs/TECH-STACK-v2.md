# Tech Stack v2: production-ready v1

**Revision 2, 2 November 2026. Owner: Akshita Johari (founder).**
Revises the original `KanoonBuddy-Tech-Stack.pdf` (6 October, revised 9 October 2026) to
match [`PRD-v2.md`](PRD-v2.md). Everything the original says that this file does not change
still stands, including the 11-step pipeline, the seven rules in CLAUDE.md section 2, the
Jev and Gemini rules, and "upload text never reaches Jev, Langfuse or Sentry". **The Tech
Stack wins over the PRD**, so this file wins over PRD-v2 where they differ.

Labels as in the PRD: **Measured**, **Checked**, **Estimate**, **Needs verification**,
**Reported** (measured by another session and written down, not re-run here).

---

## 1. What changed, at a glance

| Layer | Original | Now | Why | Label |
|---|---|---|---|---|
| Servers | One EC2 r7g.large (16 GB) runs everything | **Split**: app server (website, API, Redis, Qdrant), a **separate worker server** (OCR, virus scan), and a **separate staging server** | The original's own risk table says Qdrant memory and OCR "break first" on one box. A split also lets OCR crash without taking chat down | Decision |
| App database | PostgreSQL in Docker on the same server | **Managed PostgreSQL (AWS RDS)** with point-in-time recovery | A lost disk must not lose user accounts or payments | Decision. Cost: get a quote |
| Edge | Public IP straight to the server | **CDN and web firewall** (AWS CloudFront + AWS WAF) in front of the website and API | Abuse protection, TLS, caching of public Act and statistics pages | Decision. Cost: get a quote |
| Environments | Development and production | Development, **staging**, production | A release must be rehearsed before it reaches users | Decision |
| Email | Not specified | **Amazon SES** (Mumbai), behind `adapters/email.py` | Receipts, sign-up, password reset, usage warnings. SES starts in a sandbox; production access must be requested | Needs verification: SES availability and limits in Mumbai |
| Monitoring | Sentry + Langfuse | Add **uptime check**, **cloud alarms** (CPU, disk, memory, failed backup), a **public status page**, and **phone alerts** | Today a crash is seen only if someone looks | Decision. Vendors: owner picks after quotes |
| Rate limiting | Not specified | Redis-based limits in the API plus the firewall | Abuse and runaway cost | Decision |
| Uploads | PyMuPDF, Tesseract | Add **file-type and size checks, a page limit, a virus scan (ClamAV), and a sandboxed reader with no network** | Uploads come from the public | Needs verification: ClamAV on ARM and its memory use |
| Answer export | "Word export, as in the system architecture" | `python-docx` for Word; PDF from a server-side HTML-to-PDF library that has ARM builds | Export with citations intact | Needs verification: pick the PDF library; check ARM |
| Agents in the product | "Do not use CrewAI; LangGraph only in month 6" | **Allowed now** for the branching features only (counter-arguments, moot court, study buddy, drafting if it needs branches). The verifier and gate always run afterwards and are outside the agents' control. Record the choice in `docs/DECISIONS.md` before building (A41 proposes plain Python runners with no framework) | Owner decision of 1 Nov 2026 (CLAUDE.md section 7). The 11-step research pipeline stays a fixed pipeline | Decision |
| Search data | "Supreme Court about 2 to 3M points; BM25 must be added; all vectors voyage-4" | See section 3: counts, sparse vectors and dense models are different from the original | Reported by the data session | Reported |
| AI models | Free: Gemini 2.5 Flash-Lite | `gemini-3.5-flash-lite` (A36). Model names live in config only | 2.5 Flash-Lite is retired for new accounts | Checked live |
| Website framework | Next.js 16.4.0 | **Upgrade to the patched 16.4.3**, as its own small change with tests re-run | Security notice printed by the build | Planned; owner said "later, as its own commit" |
| Local dev data | Docker Qdrant on the external drive | Native Qdrant on the Mac's internal disk (ports 7333/7334) for the working copy | The drive links at USB 2 speed (about 34 MB/s) | Measured |

Not changed: Next.js, FastAPI, Qdrant, Redis with ARQ, Firebase Authentication, Razorpay,
Voyage, Jev, Gemini, S3 in Mumbai, Langfuse (masked), Sentry (scrubbed), GitHub Actions,
Docker Compose.

## 2. Target topology

```
                 Phone / laptop
                        |
              CloudFront + WAF  (TLS, firewall, cache for public pages)
                        |
   +--------------------+--------------------------+
   |        APP SERVER (Mumbai, ARM)               |
   |  Next.js   FastAPI   Redis   Qdrant (private) |
   +--------------------+--------------------------+
        |                |                 |
   RDS PostgreSQL     S3 (uploads,      Secrets Manager, KMS
   (point-in-time      Qdrant snapshots,
    recovery)          backups)
        |
   WORKER SERVER (no inbound; OCR + virus scan, one job at a time)

   Outside services, each behind one adapter: Firebase, Voyage, Jev, Gemini,
   Razorpay, SES, Langfuse (masked), Sentry (scrubbed)

   STAGING: one small server running the same Docker Compose with a small sample
   collection, restored from the same snapshot process as production.
```

**Why this and not the original single box.** Measured and reported counts (section 3)
shrink the vector data to about 20 GB, which fits comfortably on 16 GB with quantization
(Estimate). The reason to split is not the vectors. It is OCR, the virus scan, the
database and the website all competing for one machine's memory with no failover.

**Starting sizes (Estimate, to be replaced by measurement in step 1 and step 2):** app server
r7g.xlarge (32 GB) so Qdrant, the API and Redis have headroom; worker server small;
staging small. Original PRD and Tech Stack price quotes: r7g.large $0.0751 an hour,
r7g.xlarge $0.150 an hour (their figures, before GST, **Needs verification** on the AWS
price page); RDS, WAF, CloudFront, SES, monitoring: **get quotes**. A reserved-instance
discount can wait until the beta proves the size.

**Triggers to add a second app server and a load balancer** (any one): availability under
99.5% in a month; memory above 80% for a week; paying users cover the cost.

## 3. Search and data: what is now known

Everything in this section is **Reported** by the data session unless a different label is
given. The author of this file re-ran none of it.

| Item | Original | Now |
|---|---|---|
| English Supreme Court chunks | 2 to 3M (Estimate) | 371,247 in parquet; 371,159 in `legal_corpus_v2` |
| Supreme Court translations | not mentioned | about 742,000 chunks in parquet, **not embedded**. Not served in v1 |
| Selecting Supreme Court points | "court field name unknown" | `court = "Supreme Court of India"`. Do not use `language_code` (mostly empty, upper-case `EN`) |
| Judgment sparse vectors | must be built | exist; FastEmbed `Qdrant/bm25`; encode **queries** with `query_embed()`; 16 of 16 reproduce |
| `acts_india` sparse vectors | assumed fine | 19,835 of 74,509 Central Act points do not match the encoder (Measured, full scan of those points). Repair script `data/sparse_fix.py` (`plan`, `apply --confirm`, `restore`), **not yet run on live data**. Whether the other `acts_india` points are affected is **unknown** |
| Dense vectors | all voyage-4 | judgment chunk = voyage-4 (cosine 1.0000); one Central Act chunk = voyage-4-large (0.9994). One chunk each only |
| Payload indexes | assumed | **none exist.** Filtered scans on unindexed fields over the 11.8M-point collection time out. Indexes on `court`, `jurisdiction`, `section_number`, `act_status` and any other filter field are mandatory before real use |
| Acts scope | `acts_india`, 1,098,577 points | the working copy takes only 74,509 Central Act points (decision O7 in PRD-v2). If all of `acts_india` is served, the copy and the repair script must cover it |

**Rules that follow (new, binding on core and platform lanes):**

1. The embedding model is a **per-collection setting** in config, not one global value.
   It is set only after check 1 (which Voyage model made each group of vectors) finishes.
2. Search code must not assume one model for judgments and Acts until that check is done.
3. Every filter field has a payload index before the collection is used by the API.
4. `kanoon_v1` is built as a copy. Originals (`legal_corpus_*`, `acts_india`) are never
   written to or indexed.
5. Any repair of stored vectors: back up first, rehearse on 20 points, byte-compare a
   restore, only then run in full, and only with the owner's explicit go.
6. Retrieval quality is measured by itself (precision and recall at 10 and 50 on the test
   set) so a bad search is not mistaken for a bad answer.

## 4. Pipeline: unchanged, plus how new features use it

The research pipeline keeps its 11 steps and passage counts (50 to 10 to at most 8). New
features reuse the same trust parts. Detailed per-feature designs are in
[`FEATURES-PLAN.md`](FEATURES-PLAN.md).

| Feature | Shape | Trust path |
|---|---|---|
| Talk with a single judgment | Fixed steps: fetch judgment by record id, split by paragraph, retrieve within it, answer | Verifier checks quotes and record against **that judgment's own text**; page-anchor links |
| Drafting from templates | Fixed steps: pick template, fill fields, optional "find a supporting case" step | Any sentence citing law goes through gate and verifier; template wording is the advocate's, never generated |
| Review and compare | Fixed steps per document | Findings are labelled information, not advice; quoted clauses must exist in the document |
| Counter-arguments, moot court, study buddy | **Branching**, so orchestration is allowed (O4) | Final output **always** goes through gate then verifier; verifier code stays outside the agents |
| Saved answers, export | Not generative | The stored citation string is copied exactly as recorded; never re-typed by a model |
| Statistics pages | Database counts | Only rows with `is_final_outcome` true; live only after the 50-judgment check |

Upload chats keep their own rule: the claim-support check and any decision that touches
upload text use Gemini (paid tier), never Jev.

## 5. New stack items in detail

### 5.1 Environments and releases
- Branch to pull request to CI (tests, trust tests, lint, ARM image build) to **staging deploy** to
  manual approval to production deploy. Agents never touch a server directly (unchanged).
- Alembic migrations stay numbered and reversible; a migration must run on a copy of
  production data in staging before production.
- Feature switches are config values (a small table), not a vendor: each Launch-switch
  feature (PRD-v2 section 4.2) has one.
- Rollback: the previous container images are kept; rolling back is one command, rehearsed.

### 5.2 Backups and recovery
- PostgreSQL: managed backups with point-in-time recovery.
- Qdrant: nightly snapshot to S3 (encrypted, lifecycle rule).
- S3 uploads: versioning off for user uploads (hard delete must really delete); backups of
  backups follow the retention table counsel sets.
- A **restore drill** on a clean machine, timed, before launch and every quarter.
  Targets (Estimate): rebuild under 1 hour; at most 24 hours of data loss.

### 5.3 Security hardening
- TLS everywhere; firewall rules deny everything except the CDN to the app server.
  Qdrant, Redis and the worker are never reachable from the internet. Qdrant's dashboard only through a private tunnel.
- Secrets in AWS Secrets Manager (unchanged); admin accounts require a second factor; admin actions logged with a reason.
- Security headers on the website (content security policy, no framing, strict transport).
- Dependency and image scanning in CI (GitHub Dependabot already planned; add image scan).
- Injection defences: retrieved judgment text and uploaded text are wrapped as data, the
  answering step has no tools, and the verifier runs after. A fixed attack set
  (`evals/`) runs on every release. This is the `ai-security` review the project listed and
  has not yet done.
- Upload pipeline: type and size check, page limit, virus scan, sandboxed reader (own
  container, no network), per-user storage path, hard delete as in the original.
- Independent security test before launch (PRD-v2 gate item 5).

### 5.4 Customer-facing plumbing
- **Billing:** Razorpay subscriptions with webhook; webhook handler must be idempotent
  (store each event id) and verify the signature. Add failed-payment handling, plan change,
  cancellation. GST invoice flow: **Needs verification** with the accountant.
- **Email:** `adapters/email.py` only; no other file imports the vendor library.
- **Status and alerts:** uptime check on the public site and the API health route; alarms
  to the owner's phone.
- **Analytics:** an `events` table in our own PostgreSQL. No document text, no question
  text, no party names. No third-party scripts at launch.
- **Search engines:** server-rendered Act and statistics pages, sitemap, share cards (original).
- **Accessibility:** automated checks in CI plus a manual keyboard and screen-reader pass.

### 5.5 Performance
- Targets unchanged (first word under 3 s; full answer under 20 s; search plus re-rank
  under 800 ms; Jev decision under 800 ms or Gemini fallback; Act lookup under 500 ms;
  availability 99.5%). All remain **Estimates until measured**.
- Add a repeatable **load test** (a tool such as k6, owner's agent picks) run against
  staging before launch; the number of simultaneous users comes from beta data.
- Jev latency was about 300 ms median from a laptop in India (**Measured**, 2 Nov 2026); the
  Mumbai server's figure is not yet measured and must be re-measured.

## 6. Data model additions

The original has 17 tables and 2 collections. FEATURES-PLAN lists the exact columns per
feature. At stack level, new tables are expected for:

`plans` and `plan_limits`; `invoices`; `webhook_events` (idempotency); `feature_flags`;
`folders`, `saved_items`, `notes`; `templates`, `drafts`, `draft_versions`; `exports`;
`events` (analytics); `takedown_requests`; `support_messages` (or use the inbox only);
`admin_actions` (or extend `audit_log`); `job_runs` (background jobs). Each arrives in a
numbered, reversible migration with its feature, not all at once.

## 7. API additions

All under `/api/v1`, one error format, a request id on every response, cursor pagination
on lists (original rules). Expected groups: `/plans`, `/billing/*`, `/me/*` (consents,
export, delete), `/folders` and `/saved`, `/exports`, `/templates` and `/drafts`,
`/cases/{id}/chat`, `/admin/*` (second factor required), `/health` and `/ready` (for the
uptime check), `/events` (privacy-safe). Exact shapes go in `docs/API.md` and
`api/schemas.py` first; the web client is generated from OpenAPI (rule 3).

## 8. Revised build order

The original ten steps stand. This is the order for the widened v1.

| Step | What | Depends on |
|---|---|---|
| 0 | **Data copy and checks** (in progress): `kanoon_v1` on the Mac, payload indexes, check 1 (Voyage model per group), check 2 (voyage-4 versus voyage-4-large), sparse-repair rehearsal, decide O7 | Owner's go before any repair |
| 1 | Real hybrid search against the copy; per-collection embedding setting; five real questions through the whole pipeline; measure cost per answer and retrieval quality | Step 0 |
| 2 | Jev switches on one at a time with live comparisons; real Firebase verifier; the 200-question set drafted with the advocate | Step 1 |
| 3 | Production foundation: AWS accounts, staging, CI deploy, backups and a restore drill, monitoring, firewall, secrets | Owner buys (PRD-v2 section 6) |
| 4 | Plans, billing, accounts, consents, delete and export, feedback, admin page | Step 3; GST decision |
| 5 | Judgment reader, talk with a judgment, saved answers, export | Step 1 |
| 6 | Public pages, share cards, statistics (statistics live only after the hand check) | Step 1; advocate |
| 7 | Upload and chat with the full upload hardening | Steps 3, 5; advocate opinion; Voyage terms |
| 8 | Drafting, review and compare | Step 5; advocate-written templates |
| 9 | Private beta (20 students, 10 advocates); run the launch gate | Steps 3 to 8 |
| 10 | Branching features (counter-arguments, moot court, study buddy), Hindi, High Courts | After the gate |

Steps 4 to 8 may be built in parallel on fakes by separate lanes once step 1 shows the core
works on real questions. **Nothing is launched before the gate (PRD-v2 section 7).**

## 9. Cost: what is and is not known

The original launch estimate (about ₹7,200 to ₹7,500 a month on one server) **no longer
applies**, because the topology changed. A new total cannot be stated honestly until
quotes arrive for the managed database, firewall and CDN, email, monitoring, and the second
and third servers. Known figures carried over, with their original labels: server hourly
prices above; Gemini and Voyage per-token prices (Checked in the original); Jev about
₹0.03 per answer (Estimate); about ₹0.05 per answer for Voyage (Estimate). **Do not quote a
monthly total to anyone until a quote-based table replaces this section.**

## 10. Open decisions (additions and changes)

| Decision | Options | Working choice | What settles it |
|---|---|---|---|
| Acts scope (O7) | all of `acts_india`, or acts with status only | undecided | Count acts by jurisdiction in `acts_india`; owner decides |
| Embedding model per collection | voyage-4, voyage-4-large, mixed | per-collection setting, value pending | Check 1 and check 2 |
| Sparse repair for `acts_india` | repair, or rebuild from text | repair on a copy first | Rehearsal results; owner's go |
| Managed database size and Multi-AZ | single zone with backups, or two zones | single zone | Quote; downtime tolerance |
| CDN and firewall vendor | AWS CloudFront + WAF, or another | AWS | Quote |
| Monitoring and status-page vendors | several | undecided | Quotes |
| PDF export library | several | undecided | ARM build; quality |
| Virus scanner | ClamAV, or a managed scan | ClamAV | ARM and memory test |
| Second factor for admin | app code, or Firebase multi-factor | Firebase | Firebase docs check |
| Load-test numbers | set from beta | undecided | Beta data |
| Everything else in the original "Open decisions" table | unchanged | unchanged | as before |

## 11. Change log

- **2 Nov 2026:** first revision for the widened v1. Split topology, managed database,
  CDN and firewall, staging, email, monitoring, upload hardening, injection defences,
  orchestration allowed for branching features, per-collection embedding rule, payload
  index rule, corrected search facts, revised build order, retired the single-box cost
  total. Original PDF unchanged.
