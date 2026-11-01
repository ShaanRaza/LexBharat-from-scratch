# Architecture

Derived from **KanoonBuddy: Tech Stack** (6 Oct 2026, revised 9 Oct 2026). That PDF is the
authority; this file is the working summary. Labels: **Measured**, **Checked**,
**Dataset card**, **Competitor claim**, **Estimate**, **Needs verification**.

## Shape of the system

Everything runs in Docker Compose on **one AWS EC2 server in Mumbai (ap-south-1)**. Only
short calls go out.

```
                 User's phone or laptop
                           │ HTTPS
   ┌───────────────────────┴────────────────────────────────┐
   │  AWS EC2, Mumbai (ap-south-1) — all in Docker Compose  │
   │                                                        │
   │  Next.js website    FastAPI backend   Background worker│
   │  chat, Act and      RAG pipeline +    OCR + indexing   │
   │  stats pages        verifier + OKF    PyMuPDF/Tesseract│
   │                                                        │
   │  Qdrant             PostgreSQL        Redis queue      │
   │  kanoon_v1:         users, plans,     jobs waiting     │
   │  SC + acts_india    usage, chats      for the worker   │
   │  dense + BM25                                          │
   └───────────────────────┬────────────────────────────────┘
                           │ HTTPS, outbound only
   Firebase   Voyage AI   Jev   AI models    Razorpay   Amazon S3
   (login)    (embed,     (de-  (via         (payments) (files,
              rerank)     cide) LiteLLM)                 backups)

   Monitoring only: Langfuse (AI-call logs, masked), Sentry (errors, scrubbed)
```

Six parts in Docker; six outside services, each behind **one adapter file**. The OKF
knowledge notes are Markdown files inside the backend's code, so they need no separate
service. Uploads go browser → S3 directly with short-lived pre-signed links; the worker
reads them from there.

## Stack by layer

| Layer | v1 choice | Swap to later |
|---|---|---|
| Website | Next.js + TypeScript + Tailwind, installable PWA | Any React framework |
| Backend API | Python + FastAPI | Split into services as traffic grows |
| Background jobs | Redis + ARQ; Redis also holds the answer cache | AWS SQS + Lambda |
| Vector search | Qdrant (self-hosted, Docker), one collection `kanoon_v1` | Qdrant Cloud, bigger server |
| Keyword search | Qdrant sparse vectors (BM25), same collection | OpenSearch |
| Query embeddings | Voyage `voyage-4` | Only by re-embedding everything |
| Re-ranker | Voyage `rerank-2.5-lite`; backup open-source bge-reranker | Any reranker behind the adapter |
| AI model gateway | LiteLLM (Python library) | OpenRouter or a hosted gateway |
| AI models | Free and query rewrite: Gemini 3.5 Flash-Lite (paid tier key). Student/Pro: Gemini 3.1 Flash-Lite | Any model the gateway supports |
| Decision layer | **Jev** by TypeSafe AI (early access) | Gemini Flash-Lite with fixed choices |
| Knowledge notes | OKF-style Markdown in `knowledge/`, advocate-reviewed | A table or graph store |
| App database | PostgreSQL 16 in Docker, daily backups to S3 | AWS RDS |
| File storage | Amazon S3 (Mumbai), encrypted, auto-delete rules | — |
| OCR | PyMuPDF for text PDFs; Tesseract (English + Hindi) for scans | AWS Textract |
| Login | Firebase Authentication (email + Google) | Supabase Auth or Cognito |
| Payments | Razorpay subscriptions | — |
| Hosting | One EC2 (r7g.large, ARM) in Docker Compose | Split services, managed DB |
| Errors / monitoring | Sentry + Langfuse | Datadog or Grafana |
| Code and deploy | GitHub + GitHub Actions | Same |

## The 11-step pipeline

See [`../CLAUDE.md`](../CLAUDE.md) §4 for the canonical list. In short:

`remember → rewrite → decide (Jev) → cache → search → re-rank → gate (Jev) → answer →
verify → show → save`

Passage funnel: **search merges top 50 → re-rank keeps 10 → the gate keeps at most 8
(S1–S8)**.

Scope, filters, routing and safety run **in parallel with the Voyage embedding**, so they
add little waiting. Gate and claim checks run on all passages at once.

## Search: three ways at once

| Kind | What it finds | How | Cost |
|---|---|---|---|
| Meaning (semantic) | "bail for economic offences" finds judgments that never use those words | voyage-4 → Qdrant nearest | One Voyage call |
| Exact words (keyword) | Rare words, party names, quoted phrases | BM25 sparse vectors in the same collection | Free |
| Exact lookup (filters) | "Section 438 CrPC", a case number, an SCR citation | Qdrant payload filters on indexed fields | Free |

Meaning and keyword merge in one Qdrant call via Reciprocal Rank Fusion. Exact lookups
skip the merge and go straight to the record.

**Decided:** keyword search uses BM25 inside Qdrant. This settles the PRD's open choice
between PostgreSQL full-text and Qdrant sparse vectors, and it covers the failure state
"Voyage API is down" — keyword search and exact lookups keep working, labelled
*keyword results only*.

## Decision layer: Jev

Jev makes every **fixed-choice** decision; Gemini still writes all prose.

| Step | Question | Choices | Effect |
|---|---|---|---|
| Scope check (pre-search) | Can we answer this? | in scope / needs a High Court / needs a tribunal / after the snapshot date / not a legal question | Anything but "in scope" shows the coverage message. No search, no writing cost |
| Filters (pre-search) | Which court, years, Act? | Court and year from fixed lists; Act from up to 20 keyword-matched candidates | Narrows the Qdrant query |
| Model routing | Easy or hard? | easy / hard | **Off at launch** |
| Answer-or-refuse gate (post-rerank) | Does each passage help? | answers it / partly / not relevant | Below 0.6 for all → "not found", nothing written |
| Claim-support check (post-writing) | Does this passage support this sentence? | supports / partly / does not support | "Does not support" removes and logs the citation; "partly" shows a warning mark |
| Safety check | What kind of request is this? | normal / personal legal advice / trying to trick the AI | Personal advice gets a stronger disclaimer; tricks are blocked |
| Uploads | What is this document, is the OCR readable? | bail application / agreement / notice / judgment / other; readable or not | Unreadable files fail early and are not charged |

**Safeguards.** One adapter (`adapters/decisions.py`), a per-use on/off switch in config,
and a Gemini Flash-Lite fallback with the same fixed choices if Jev is down or slower than
800 ms. The three free verifier checks always run, Jev or not. Jev's servers are on the US
West Coast, so **upload text never goes to Jev** — Gemini (paid tier) handles those checks.

Cost: about ₹0.03 per answer (Estimate).

## Knowledge notes (OKF)

A few hundred reviewed Markdown files in `knowledge/`, carrying facts that search cannot
get right on its own — above all **which old law maps to which new law** (IPC → BNS,
CrPC → BNSS, Evidence Act → BSA, from 1 July 2024). Old judgments do not know the law
changed, so retrieval alone cannot fix this.

| | Knowledge notes | RAG search |
|---|---|---|
| Holds | Checked facts: law maps, leading cases, limitation periods, coverage rules | All SC judgments and `acts_india` |
| Size | A few hundred files | Millions of chunks |
| Found by | Jev's decide step picks the notes that apply | Meaning + keyword search, re-rank, Jev gate |
| Shown to the AI as | "Background notes" | "Passages S1–S8" |

**A note never counts as a citation by itself.** When an answer uses a note, it cites the
judgment or section the note points to, and the verifier checks that record as usual.
Only notes with `status: reviewed` are used in live answers. See
[`../knowledge/index.md`](../knowledge/index.md).

## Caching

Redis, exact match on (rewritten query + filters + model name), 7 days (Estimate).
Only answers that **passed verification** are cached. Upload chats are **never** cached.
Clear the cache when a data refresh adds new judgments. Cache hits are free and do not
count against the user's limit.

## Public pages (free, no login)

The PRD's main route to the first 100 users: free database-filter pages with no Voyage,
Jev or AI writing call.

| Page | Address | Shows |
|---|---|---|
| Act section | `/acts/{act}/{section}` | Section text, in-force status, related knowledge notes |
| Outcome statistics | `/stats/supreme-court/{year}` | How SC cases that year were decided |
| Statistic detail | `/stats/supreme-court/{year}/{outcome}` | The count, with links to example judgments |

Server-rendered by Next.js, listed in `sitemap.xml`, each with a share card carrying the
source, data-as-of date and CC BY credit.

**Supreme Court stats go live only after the 50-judgment hand check passes.** High Court
stats wait for their own check in Phase 2.

## Uploads

1. Browser asks the backend for a pre-signed S3 link and uploads straight to S3.
2. Backend creates an upload record and queues a Redis job.
   Status: `uploaded → extracting → indexing → ready`, or `failed` with a reason.
3. Worker samples pages for a text layer: PyMuPDF for text PDFs, python-docx for Word,
   Tesseract OCR (English + Hindi) for scans. Low OCR quality → `failed`, not charged.
4. Text is chunked; **every chunk keeps its page number and start/end character
   positions**, so a citation can jump to and highlight the exact passage.
5. Chunks embed with voyage-4 (free local model as fallback) into the shared private
   `user_documents` collection. Every chunk carries `user_id` and `document_id`, and
   every search filters on both.
6. Answers cite page numbers in the user's own file and label "your document says"
   separately from "Supreme Court judgments say".

The worker runs in its own container, **one job at a time, capped at 1 CPU**, so chat
stays fast.

**Switched off for users at launch** unless the 20 interviews and the advocate's written
legal opinion support it.

## One server: what that means

No failover. Accepted at launch to keep cost low. To reach 99.5%: EC2 automatic recovery,
daily snapshots to S3, and a written rebuild plan (target under 1 hour). A second server
behind a load balancer only when paying users cover it.

Running cost at launch: about **₹7,200–₹7,500 a month**, covered by about 21 paying users
at the PRD's blended ₹349 (Estimate).
