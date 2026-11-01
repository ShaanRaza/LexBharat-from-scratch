# Data model

**18 PostgreSQL tables and 2 Qdrant collections** in v1 (17 + `matters`, migration 0006).

Conventions: IDs are UUIDs; every table has `created_at` and `updated_at`. **There is no
password column anywhere** — Firebase holds passwords and these tables point to the
Firebase user ID. Drafting and sandbox tables from the architecture doc are added when
those features are built.

## Accounts and billing

| Table | Key fields |
|---|---|
| `users` | id, firebase_uid (unique), email, name, role (advocate / student / in-house / other), plan, status |
| `subscriptions` | id, user_id or organisation_id, plan, seats, razorpay_subscription_id, status, period_start, period_end |
| `usage_daily` | user_id, date, feature, requests, tokens_in, tokens_out, cost_estimate |
| `organisations` | id, name, owner_user_id, plan (chambers, ₹299 per user a month), seats (minimum 3) |
| `memberships` | organisation_id, user_id, role (admin / member), status (invited / active / removed) |
| `consents` | id, user_id, notice_version, purpose, given_at, withdrawn_at |

## Matters, and the two schema rules

| Table | Key fields |
|---|---|
| `matters` | id, user_id, title, kind (matter / project), status (active / archived), archived_at, created_at, updated_at |

A matter is one case or project that saved answers, uploads, drafts, notes and remembered
facts hang off (PRD-v2 O11). One table. "Matter" for advocates and "Project" for students
is the `kind` label, not a second feature.

**Convention 1 — `matter_id` from the first migration.** Every table that holds user work
carries a **nullable** `matter_id` (foreign key to `matters`, `ON DELETE SET NULL`) in the
migration that **creates** it, even if the screen that uses it ships later. Today that is
`conversations`, `messages` and `documents` (added in 0006). Tables not yet created that must
follow: `saved_items`, `notes`, `drafts`, `exports`, `matter_facts`. Retrofitting the column
across a live schema is the migration that goes wrong.

**Convention 2 — every stored answer carries the provenance flag.** `messages` has
`shaped_by_upload` and `shaped_by_matter_fact` (both `NOT NULL`, **no default**). The
pipeline decides them when the answer is produced and step 11 (Save) writes them in the same
insert; nothing derives them later. Sharing (PRD-v2 O14) is allowed only when both are false,
and an answer shaped by a matter fact is never put in the shared answer cache. Any future
table that stores an answer (saved copies, exports, share links) copies these two columns.

Not created yet, on purpose: memory tables (`memory_preferences`, `matter_facts`). Memory
retention (O13) is not settled.

## AI spend view

`ai_spend_daily` (a view, migration 0007) lists, per day and feature, the calls and tokens
of every paid model call we can count: answers (from `messages`, cache hits excluded) and
the two helpers `improve` and `followups` (from `usage_daily`, which stores their tokens
under their own feature name). No money is stored: it is worked out when read from
`AI_PRICE_IN_PER_MTOK` / `AI_PRICE_OUT_PER_MTOK`. **The answer meter counts only the
`research` rows**, so helper calls never use the answer limit. Not counted yet (existing
gap): tokens of the rewrite, gate and decision calls.

## Conversations and trust

| Table | Key fields |
|---|---|
| `conversations` | id, user_id, module (research / document), document_id (if any), **matter_id (nullable)**, title, rolling_summary, message_count |
| `messages` | id, conversation_id, **matter_id (nullable)**, **shaped_by_upload**, **shaped_by_matter_fact**, role, content, rewritten_query, model, tokens_in, tokens_out, latency_ms, from_cache, scope, route (easy/hard), safety, jev_used |
| `message_sources` | message_id, source_id (S1–S8), record_id, chunk_id, rank, rerank_score, verified (yes/no), relevance (from the Jev gate), support (supports / partly / does not), support_confidence |
| `invented_citation_log` | id, message_id, query, model, cited_text, reason (not retrieved / record missing / quote not found / claim not supported) |
| `feedback` | message_id, user_id, rating, reason, comment |

`invented_citation_log` is the trust metric's source. The rate of answers with a removed
citation is a **launch metric: target under 0.5%**, shown on the admin page and checked on
every release against the 200-question test set.

## Uploads

| Table | Key fields |
|---|---|
| `documents` | id, user_id, filename, mime_type, size_bytes, page_count, status (uploaded / extracting / indexing / ready / failed), fail_reason, ocr_used, storage_path, expires_at, deleted_at |
| `document_chunks` | id, document_id, page_no, char_start, char_end, text, vector_id |

`page_no`, `char_start` and `char_end` are what let a citation jump to and highlight the
exact passage in the viewer. Do not drop them.

## Corpus copy for fast reading

Loaded once from parquet with DuckDB. The Supreme Court is small enough to sit in
PostgreSQL; High Courts in Phase 2 may be too large and may have to be served from parquet
or S3 instead (Needs verification).

| Table | Key fields |
|---|---|
| `cases` | record_id, title, court, decision_date, case_number, citation, disposition (raw), outcome_label (allowed / partly allowed / dismissed / disposed of / other), is_final_outcome, outcome_checked (in the hand-check sample), pdf_url, full_text |
| `act_sections` | record_id, act_name, act_year, section_number, section_title, text, in_force, act_status, source_url |
| `court_coverage` | court, snapshot_version, data_as_of, points, live (yes/no), stats_live (yes/no) |

`court_coverage` holds the **data-as-of date per court**, shown on every result, stats page
and Act page.

## Records

| Table | Key fields |
|---|---|
| `audit_log` | id, user_id, action (login / upload / delete / export / admin view), target_id, ip, request_id, at |

**`audit_log` never stores document text.**

Judges and party names are left out of display everywhere — the PRD's audit found those
fields unreliable.

## Qdrant collections

| Collection | Vectors | Payload fields used as filters |
|---|---|---|
| `kanoon_v1` | dense (voyage-4) + sparse (BM25) | record_id, source_type (judgment / act), court, year, citation, case_number, act_name, section_number, in_force, act_status, outcome_label, is_final_outcome |
| `user_documents` | dense (voyage-4; free local model as fallback) | user_id, document_id, page_no, char_start, char_end |

**Every query against `user_documents` goes through one shared data-access function that
always adds the `user_id` filter.** No feature writes its own upload query.

### Building `kanoon_v1`

The local Qdrant holds all 32.5M vectors. v1 needs only the Supreme Court and
`acts_india`, so build one new, small collection and ship only that:

1. Read Supreme Court points out of **`legal_corpus_v2`** with the filter
   `court_type = "supreme_court"`, with their vectors: **371,159 points** (Measured,
   13 Oct 2026). `legal_corpus_v1` holds no Supreme Court points.
2. Read matching chunk text from the parquet files with DuckDB and compute BM25 sparse (judgment sparse vectors already exist and reproduce, and some `acts_india` ones are wrong: see docs/DATASET.md, 2 Nov 2026 findings)
   vectors (fastembed, free, local).
3. Write both into `kanoon_v1` with two named vectors: dense (the existing voyage-4
   vectors, **no re-embedding**) and sparse. Copy `acts_india` the same way.
4. Turn on **scalar quantization** — about a quarter of the memory; keep full vectors on
   disk.
5. Snapshot → S3 → restore on the EC2 server, then delete the snapshot file to free disk.

Size: `acts_india` is 1,098,577 points and the Supreme Court 371,159 (both Measured).
At ~13.5 KB per point (Estimate), that's about **20 GB of disk** for all of `acts_india`,
or about **6 GB** if v1 serves Central Acts only (see `DECISIONS.md`). Memory with
quantization: well under the earlier 4–5 GB estimate (Needs verification by load test).
