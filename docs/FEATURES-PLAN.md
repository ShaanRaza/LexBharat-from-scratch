# Features plan (planning only, nothing here is built)

Status: **revision 2, 2 Nov 2026 (later), aligned with [`PRD-v2.md`](PRD-v2.md) and
[`TECH-STACK-v2.md`](TECH-STACK-v2.md).** Where this file and those two disagree, they win
(the Tech Stack wins over the PRD). No code was written for this document. Facts about the
repo were read from the files named; anything not checked is marked **unverified**. Evidence
labels follow CLAUDE.md §9.5, plus **Reported** (measured by another session, not re-run
here) as defined in PRD-v2.

The product is called **LexBharat** (O8). The name always comes from config (`PRODUCT_NAME`,
`NEXT_PUBLIC_PRODUCT_NAME`); this file says "the product".

**This plan writes no legal wording.** Every sentence a user would read about advice,
privilege, BCI Rule 36, consent, retention, coverage or "what the tick means" is listed under
"Owner decisions" instead of being drafted here. Template names in feature 4 are names only.

## What changed in this revision

| Change | Why (source) |
|---|---|
| **Prices and plan limits are config only.** Plans in the code are labelled placeholders; no price or limit number is written in a feature, a test expectation or a page | O10: pricing deferred; ₹199, ₹499, ₹299 stay hypotheses (PRD-v2 §2) |
| New feature **11 Coverage page** (measured counts only, "not in our dataset" on a miss) | O7, PRD-v2 §4.2 |
| New features **12 Saved answers, folders, notes, export to Word/PDF** and **13 Onboarding, help centre, support** | PRD-v2 §4.2 lists them as Launch |
| Email vendor settled: **Amazon SES behind `adapters/email.py`** (owner decision #21 removed) | TECH-STACK-v2 §1 (SES availability in Mumbai: Needs verification) |
| Admin: **second factor required, every admin view of user data logged with a reason** (Firebase multi-factor is the working choice) | PRD-v2 §5.2, TECH-STACK-v2 §10 |
| Drafting: **template wording is the advocate's and is never generated.** The model only fills the user's fields and runs the optional "find a supporting case" step | TECH-STACK-v2 §4 |
| Feature switches: a **`feature_flags` table** whose default comes from settings | TECH-STACK-v2 §5.1, §6 (choice recorded as A45) |
| Offline feature is **offline reading of saved answers**, plus resumable uploads, with a page-weight budget | PRD-v2 §4.2 |
| Build order mapped to **TECH-STACK-v2 §8** (steps 4 to 10); features 4 to 8 may be built in parallel on fakes once step 1 shows the core works | TECH-STACK-v2 §8 |
| A **second frozen test set** per new feature, and the **prompt-injection test set** on every feature that writes legal text | PRD-v2 §5.5, §7 items 13 |
| Branching features moved to "after the launch gate" | PRD-v2 §4.3 |
| Costs point to PRD-v2 §6 (buy list); no total is quoted | TECH-STACK-v2 §9 |

---

## 0. Rules every feature follows

### 0.1 The trust boundary for anything that writes legal text

The citation verifier (`core/verify.py`) and the gate (`core/gate.py`) belong to the **trust
lane**. No feature lane edits them. A feature that produces model-written text follows this
shape, in plain Python that the feature's own code runs:

```
user input
   │
   ▼
 search → re-rank → GATE  ── passages labelled S1..S8 (the model sees only these)
   │
   ▼
 model writes (output is DATA, never trusted; the answering step has no tools)
   │
   ▼
 VERIFY (checks 1-4, the same function chat uses)  ── failed citations removed + logged
   │
   ▼
 sealed result (HMAC, key never given to a feature)  ──►  only sealed results can be
                                                           shown, saved as final, exported
```

What keeps this outside any agent's control:

1. **The verifier is called by the runner, never offered to a model as a tool.** A model or
   agent receives passages and writes; it cannot call, skip, reorder or configure `verify()`.
2. **Only `verify()` can create a sealed result.** Features may not import `seal_answer`,
   `_check_seal` or build `VerifiedAnswer` themselves. A grep test (like the vendor boundary
   test in `tests/core/test_adapters.py`) fails the build if they do.
3. **Output boundaries accept sealed results only.** Today that is `show()` (`core/show.py`).
   Features 4, 5, 6, 10 and 12 add the same guard for documents: a `verify_sections()` in
   `core/verify.py` (trust lane) returns a sealed `VerifiedDocument`; Word/PDF export and
   "save as final" refuse anything unsealed.
4. **Text the model did not write is labelled as such** (template text, the user's own text).
   Labels are owner wording.
5. **Uploads and user-entered facts** are treated like uploaded documents (CLAUDE.md §6): never
   to Jev, Langfuse or Sentry; claim-support runs on the Gemini paid tier; every query goes
   through the one `user_id`-filtered function in `core/uploads.py`.
6. **Retrieved judgment text and uploaded text are wrapped as data, never instructions**
   (TECH-STACK-v2 §5.3). The fixed attack set in `evals/` runs against every feature that
   writes legal text: no answer may skip the verifier, reveal another user's data, or follow an
   instruction found inside a document (PRD-v2 §5.2, launch gate item 13).
7. If a feature uses agent orchestration it follows A41 in `docs/DECISIONS.md`.

A feature with **no model-written text** (billing, deletion, admin, public pages, coverage,
export, PWA) says so and names the test that proves no legal text can slip in.

### 0.2 Data prerequisites (TECH-STACK-v2 §3, binding on core and platform)

Features 6, 7, 10 and 11 read the real collections. None may go live before step 0 of the
build order finishes. The relevant rules:

- The embedding model is a **per-collection setting** in config; search code must not assume
  one model for judgments and Acts until the voyage-4 vs voyage-4-large check is done (Reported:
  a judgment chunk matched voyage-4, one Central Act chunk matched voyage-4-large; one chunk
  each tested).
- **Every filter field has a payload index** before the API uses the collection (Reported: none
  exist; filtered scans over the 11.8M-point collection time out). Fields used here: `court`,
  `jurisdiction`, `section_number`, `act_status`, `record_id`, `case_number`.
- English Supreme Court is selected with `court = "Supreme Court of India"`, never
  `language_code` (the store already refuses it, A38).
- Hybrid search exists behind `adapters/qdrant.py` (A38) but has **never run against a live
  Qdrant** (not verified).
- Sparse vectors for 19,835 of 74,509 Central Act points do not match the encoder (Measured, full
  scan); the repair script has not been run on live data (A39).
- Any repair of stored vectors: back up, rehearse on 20 points, byte-compare a restore, owner's go.

### 0.3 Config-only values (pricing is deferred, O10)

These live in settings or the database, never in code, tests' expected business values, or
page text. A guard test per lane (same pattern as `web/src/__tests__/guards.test.ts`) fails
on a literal.

| Value | Where it lives | Note |
|---|---|---|
| Plan names, monthly prices, annual prices, seat minimum | `plans` table, seeded from settings; **placeholder plans** until O10 | Billing is built and tested with placeholder plans |
| Per-plan, per-feature monthly limits | `plan_limits` table, default from `PLAN_LIMIT_*` (today all unset, A20) | Shown to users in plain numbers read from here |
| GST included or excluded; GST rate | settings | O9 open (accountant) |
| Feature switches | `feature_flags` table, default from `FEATURE_*` settings (all off) | A45 |
| Model names, thresholds, passage counts | settings (existing) | Passage counts 50 → 10 → at most 8 stay (decision file) |
| Product name, collection name, data-as-of date, snapshot version | settings (existing) | |
| Coverage figures | `coverage_*` tables built by a measuring script (feature 11) | Never typed by hand |

Web pages read all of these from the API (`GET /plans`, `GET /coverage`, `GET /me`). The
**public pricing page is behind a feature switch and stays off until O10 is decided**; before
then it can only render placeholder plans labelled "Sample".

### 0.4 Cross-cutting work done once, before feature 1

| Item | Lane |
|---|---|
| `feature_flags` table + `core/flags.py` (`is_on(name)`), default from `FEATURE_*` settings | platform |
| `core/plans.py`: `limit_for(plan, feature)` reads `plan_limits`; unset means "not configured" (A20) | core |
| Usage meter keyed by `(user, feature, month)`; research keeps working (`usage_daily` already has `feature`, `docs/DATA-MODEL.md`) | platform |
| Rate limits in Redis per user and per address on every new write route (TECH-STACK-v2 §1) | platform |
| Fakes registry so `docker compose up` runs every feature with no keys (Fakes refuse `ENVIRONMENT=production`, `adapters/guard.py`) | platform |
| `events` table for privacy-safe product analytics: **never document text, question text or party names** (PRD-v2 §5.4) | platform |
| Admin identity with second factor and a reason on every view of user data | platform |
| New shared web components, styled only from `web/src/design/tokens.css` (list below) | web |

**New shared web components:** `PriceCard`, `PlanBadge`, `UsageBar`, `ConfirmDialog`,
`DataTable`, `Tabs`, `Toast`, `FormSection`, `ReportDialog`, `RatingButtons`,
`DocumentEditorFrame` (wraps the editor so editor logic never imports styling), `ShareCard`,
`CoverageTable`, `FolderTree`, `EmptyState`. `web/src/__tests__/guards.test.ts` already fails
on a hard-coded colour, font or inline style, so every feature inherits that check. UI and
logic stay apart: pipeline, drafting, review and chat logic live in `core/` and `web/src/lib/`
and import nothing from styling.

**Accessibility (PRD-v2 §5.4, gate item 15):** the core flows (ask, read an answer, open a
citation, pay) get a keyboard and screen-reader test; target WCAG 2.2 AA is a *proposed*
target, not decided.

### 0.5 Per-feature template

Each feature answers the same questions. "Steps" means the 11 pipeline steps in CLAUDE.md §4
(Remember, Rewrite, Decide, Cache, Search, Re-rank, Gate, Answer, Verify, Show, Save). Sizes:
**S** ≈ days, **M** ≈ 1-2 weeks, **L** ≈ 3+ weeks of one agent lane. All sizes are
**Estimates**. "Switch gate" is the PRD-v2 §4.2 condition for turning the feature on.

---

## 1. Plans, billing, pricing page, usage meter

| | |
|---|---|
| **Lanes** | platform (billing, routes, migrations), core (`core/plans.py`, usage), web (pricing + account billing), trust (reviews the usage-check ordering only) |
| **Adds (API)** | `GET /plans` (public: names, prices, limits in numbers, all read from the tables), `POST /billing/subscriptions`, `POST /billing/subscriptions/{id}/cancel`, `POST /billing/subscriptions/{id}/change-plan`, `GET /me/billing` (plan, period, next charge, invoices), real `POST /billing/webhook` (a stub that returns "not built" today, `api/routes/misc.py:49`) |
| **Adds (files)** | `adapters/razorpay.py` gains `create_subscription`, `cancel_subscription`, `change_plan`, `fetch_invoice` + `FakePayments` (only `verify_webhook` exists today); `core/plans.py`; `core/billing.py` (webhook event → subscription state, **idempotent: each event id stored**, TECH-STACK-v2 §5.4); `adapters/email.py` receipts (feature 8 shares it); `migrations/0006_billing.py` (`plans`, `plan_limits`, `invoices`, `webhook_events` with unique event id, `plan_changes`); `api/routes/billing.py` |
| **Adds (web)** | `/pricing` (public, server-rendered, **behind a switch until O10**), `/account/billing` (plan, cancel, change, receipts, failed-payment banner), plan badge, usage meter wired to `GET /me` (the line from the web walk-through exists, `web/src/components/chat/UsageMeter.tsx`) |
| **Fakes** | `FakePayments`: fake subscription id, a fake checkout that "pays" or "fails" on a button, webhook bodies **signed with a test secret** so the real `verify_webhook` runs in every test. **Placeholder plans** seeded from settings, labelled "Sample". `FakeEmail` records receipts. No Razorpay key used |
| **Verifier / gate** | No model-written text. Proof: a test that billing and plans modules import no LLM adapter. The usage check still runs **before any AI call**, and a cache hit does not count |
| **Steps touched** | The usage check (before step 1), step 4 (cache hit does not count), step 11 (the meter counts one answer) |
| **Tests that try to break it** | forged / replayed / out-of-order webhook (signature checked, idempotent); webhook for a deleted user; downgrade mid-month keeps the used count; limit hit at exactly N and N+1 under 20 parallel requests; cache hit not counted; failed payment never upgrades; plan from client input ignored; **price and limits on `/pricing` equal what is sent to Razorpay and what is enforced (one source: the tables)**; **no price or limit literal anywhere in code or page text** (guard test); invoice carries what the accountant requires (O9, not testable until decided) |
| **Size** | **L** (renewals, failures, cancel, plan change) |
| **Switch gate (PRD-v2 §4.2)** | GST decision (O9); refund policy; **test-mode run end to end** |
| **Needs real data / money** | Razorpay business account and KYC (start now; fee about 2% is the PRD's own figure, **Needs verification**), plans created in the Razorpay dashboard, accountant for GST and invoice rules, SES production access. **Prices and limit numbers: deferred by the owner (O10)** |

---

## 2. Account delete, data export, consent notice with version

| | |
|---|---|
| **Lanes** | platform (routes, jobs), core (adapters: Firebase admin delete, S3/Qdrant delete), web (account page), trust (isolation tests) |
| **Adds (API)** | implement `GET /me/export` and `DELETE /me` (both 501 today, `api/routes/me.py:54,59`); `GET /legal/notice` (current notice version + text from `legal/`); `POST /me/consents` exists; re-consent check on login |
| **Adds (files)** | `workers/delete_account.py` (one job: S3 object, PostgreSQL text, Qdrant vectors by `document_id`, Firebase user, Razorpay cancel, then an audit row); nightly `workers/leftover_check.py`; `adapters/firebase.py` gains `delete_user`; `adapters/s3.py` and `qdrant.py` gain delete-by-user; `core/export.py` (export bundle); `migrations/0007_deletion_requests.py`; `adapters/email.py` sends confirmation |
| **Adds (web)** | `/account` (profile, consents, withdraw, export, delete with `ConfirmDialog`), re-consent screen when the notice version changes |
| **Fakes** | `FakeFirebaseAdmin`, in-memory S3/Qdrant fakes (exist), `FakeClock` for the nightly check, fake bucket with an expiring link, `FakeEmail` |
| **Verifier / gate** | No model-written text. The export contains the user's stored answers **as stored**; it re-labels nothing. Test: an answer whose citation was removed does not get it back in the export |
| **Steps touched** | Step 11 (what Save stored is what export returns) |
| **Tests that try to break it** | user A deletes: nothing of B changes; delete is hard (row counts, S3 keys, Qdrant filter by `user_id` all zero); delete during indexing; delete twice; Razorpay or Firebase down (job retries, user not told "done" early); export of A never holds B's rows; export excludes upload text unless the owner decides otherwise; payment and invoice records kept; `audit_log` row holds no document text |
| **Size** | **M** |
| **Switch gate** | Counsel decides what `DELETE /me` keeps (invoices) |
| **Needs real data / money** | **Counsel:** retention periods (all blank in `docs/RETENTION.md`), consent notice and version document in `legal/` (do not exist), privacy policy, terms. Real Firebase project, S3 bucket, Razorpay (feature 1) to test real deletes |

---

## 3. "Report a wrong answer", thumbs-up rating, admin page

| | |
|---|---|
| **Lanes** | platform (routes, admin auth, migrations), web (buttons + admin screens), trust (reads the log; owns the 200-question runner hook) |
| **Adds (API)** | extend `POST /feedback` (exists, `api/routes/conversations.py:107`) with `kind` = `rating` or `report`; `GET /admin/reports`, `PATCH /admin/reports/{id}`, `GET /admin/invented-citations`, `GET /admin/metrics`, `POST /admin/evals/run`, `GET /admin/costs` (daily cost per answer, hard-stop setting, PRD-v2 §5.1) |
| **Adds (files)** | `migrations/0008_reports.py` (`feedback` exists; add kind, status, reviewed_by); `api/routes/admin.py`; `api/admin_auth.py` (second factor via Firebase multi-factor, **working choice, Needs verification** against Firebase docs); `core/reports.py`; admin views extend `audit_log` with a **reason** field (or a separate `admin_actions` table, TECH-STACK-v2 §6; choice recorded as A45) |
| **Adds (web)** | `RatingButtons` and `ReportDialog` under each answer; `/admin`, `/admin/reports/[id]`, `/admin/citations`, `/admin/evals`; never linked from the public top bar |
| **Fakes** | `FakeRepo` with seeded reports; fake admin identity with a fake second factor |
| **Verifier / gate** | No model text. A report **references** a message and its `message_sources`; the admin view re-displays what was stored. A report saying "citation X is wrong" is an input to `invented_citation_log` review and **never** automatically changes a sealed answer |
| **Steps touched** | Step 11 (feedback saved against `message_id`); reads stored outputs of steps 7-9 |
| **Tests that try to break it** | non-admin gets 403 on every `/admin/*`; admin without second factor is refused; admin view without a reason is refused; user rates or reports **someone else's** message; a report on an upload-chat message must not carry upload text to the admin page; rating spam (rate limit); HTML in a report comment is escaped; every admin view lands in `audit_log`; a report cannot flip `verified`; double-report |
| **Size** | **M** |
| **Needs real data / money** | Report reasons and every dialog sentence (owner wording). The 200-question set (100 real, 50 Act lookups, 50 traps) signed off and frozen by the advocate advisor (PRD-v2 §5.5). Who the admins are (owner). Advocate advisor retainer for reviewing wrong-answer reports |

---

## 4. Drafting from templates

**Template names only** (proposed for an advocate to keep, rename or replace; no template text
is written here and **a name is not a statement that the document is valid or complete**).

1. Legal notice (general demand) 2. Reply to a legal notice 3. Legal notice for a dishonoured
cheque 4. Rent agreement (residential) 5. Leave and licence agreement 6. Sale agreement
(immovable property) 7. Employment agreement 8. Non-disclosure agreement 9. Memorandum of
understanding 10. Partnership deed 11. General power of attorney 12. Will 13. Affidavit
(general) 14. Vakalatnama 15. Plaint (civil suit) 16. Written statement 17. Regular bail
application 18. Anticipatory bail application 19. Consumer complaint 20. RTI application

| | |
|---|---|
| **Lanes** | core (`core/features/drafting.py`, prompts as files), trust (`verify_sections()`, sealed `VerifiedDocument`), platform (routes, migrations, export), web (editor page) |
| **Adds (API)** | `GET /templates`, `GET /templates/{id}` (fields to fill), `POST /drafts`, `GET/PATCH /drafts/{id}`, `POST /drafts/{id}/fill` (field filling), `POST /drafts/{id}/support` (optional "find a supporting case", streams), `POST /drafts/{id}/export` (docx/pdf, sealed only) |
| **Adds (files)** | `core/features/drafting.py` (fixed steps: pick template → fill fields → optional supporting case, TECH-STACK-v2 §4); `core/prompts/draft_*.txt`; `templates/` folder of owner-supplied files with metadata (`name`, `reviewed_by`, `version`), **empty until the advocate supplies text**; shares the export code with feature 12; `migrations/0009_drafts.py` (`templates`, `drafts`, `draft_versions`); web `/templates`, `/drafts/[id]`; editor library (TipTap was the original suggestion, **unverified** licence terms) |
| **Fakes** | `FakeLLM` (fills fields, returns a supporting passage with `[S1]`); three **placeholder templates** labelled "Sample template (not legal text)"; `FakeDocxExporter` |
| **Verifier / gate** | Three kinds of text in a draft. **(a) Template wording:** the advocate's, **never generated or rewritten by the model**, shipped with `reviewed_by`. **(b) The user's own text** (facts, names, dates): the user's; never to Jev/Langfuse/Sentry; claim-support on Gemini. **(c) Model-written text:** limited to field-filling suggestions and the optional supporting-case text; it goes through retrieval → gate → `verify_sections()`. Any sentence naming an Act, section or case needs an `[S#]` that passes checks 1-4 or it is removed and logged. Export refuses a draft whose model-written parts are not sealed |
| **Steps touched** | Rewrite (facts → query), Decide (scope), Search, Re-rank, Gate, Answer (supporting case / fills), Verify, Show, Save (versions), usage meter |
| **Tests that try to break it** | model invents a section → removed and logged; real case not retrieved → fails check 1; a model edit that changes template wording is rejected (template text compared byte for byte against the stored template); user types a fake citation into their own text (must **not** get a tick); injection inside a field; edit after sealing then export; missing fields; two users, same template, no leak; party names typed by the user never appear in logs; a **second frozen test set for drafting** (PRD-v2 §5.5) |
| **Size** | **L** |
| **Switch gate** | Template wording written or signed off by the advocate advisor; drafts that cite law go through the verifier |
| **Needs real data / money** | **Template legal text and its review (owner / advocate).** Gemini paid-tier cost per draft (not measured). Editor and Word export libraries |

**Open design problem:** chat refuses answers with zero surviving citations (A14); drafting prose
mostly cites nothing. Proposed rule for owner approval: **any model-written sentence that states
what the law is must be cited and verified; template wording and the user's own text are not
cited.** Detecting "states what the law is" depends on the heuristic `_unretrieved_authority`
in `core/verify.py`; its recall on real drafts is **not measured**.

---

## 5. Review and compare drafts

| | |
|---|---|
| **Lanes** | core (`core/features/review.py`, `compare.py`), trust (quote check against the user's own document), platform (routes, upload pipeline reuse), web |
| **Adds (API)** | `POST /reviews`, `GET /reviews/{id}`, `POST /compare`, `GET /compare/{id}` |
| **Adds (files)** | `core/features/review.py` (checklist findings, **labelled information, not advice**), `core/features/compare.py` (deterministic text diff **first**, model explanation second), `core/prompts/review_*.txt`; `migrations/0010_reviews.py`; web `/review`, `/compare` |
| **Fakes** | `FakeLLM` canned findings; two sample documents; the upload side of `FakeVectorStore` |
| **Verifier / gate** | A finding makes two kinds of claim. *About the document*: it must quote the user's document and the quote is checked by check 3 **against that document's stored text** (check 2: the record exists in `user_documents` for this `user_id`); **quoted clauses must exist in the document** (TECH-STACK-v2 §4). *About the law*: it must cite a gated passage from the law collection and pass checks 1-4. Findings with neither are dropped. Claim-support on Gemini, never Jev |
| **Steps touched** | Search (law side + the user's document via the `user_id` function), Re-rank, Gate, Answer, Verify, Show, Save, usage meter |
| **Tests that try to break it** | review A's document as user B returns nothing; quote not in the document → removed; finding cites a case not retrieved → removed; identical files compare as "no differences" with **no model call**; whitespace-only difference; huge document (limit message); unreadable scan → "could not read this file", **meter not charged** (UX-COPY); injection hidden in the uploaded draft; upload text absent from Langfuse/Sentry fixtures; **second frozen test set for review**; advocate samples 20 outputs (PRD gate) |
| **Size** | **L** |
| **Switch gate** | Risk flags labelled information, not advice; the advocate samples 20 outputs; **plus the upload gate below** (review runs on uploads) |
| **Needs real data / money** | Upload pipeline with the full hardening (type and size check, page limit, ClamAV virus scan, sandboxed reader with no network: ClamAV on ARM is **Needs verification**, TECH-STACK-v2 §1); OCR; advocate's written opinion and Voyage's written no-training terms (upload switch gate, PRD-v2 §4.2); review checklists are legal content for the advocate; privilege warning wording (owner) |

---

## 6. Talk with a single judgment

| | |
|---|---|
| **Lanes** | core (filter the 11 steps to one record), web (judgment page gets a chat panel), platform (route) |
| **Adds (API)** | `POST /conversations` accepts `record_id` (module `judgment`), same `POST /conversations/{id}/messages` stream; plus the summary / issues / ratio entry points, `POST /cases/{id}/chat` (TECH-STACK-v2 §7) |
| **Adds (files)** | `core/search.py` accepts a `record_id` payload filter (retrieval **within** the judgment); `core/decide.py` skips the scope check; `core/features/judgment_chat.py` (fixed steps: fetch by record id → split by paragraph → retrieve within it → answer); web `JudgmentChat` on `/cases/[id]` reusing `ChatScreen` pieces |
| **Fakes** | `FakeVectorStore` with one 40-paragraph judgment; the fake pipeline |
| **Verifier / gate** | **Unchanged**: the normal pipeline with a tighter filter. All four checks run against **that judgment's own paragraphs**; check 1 additionally asserts the cited `record_id` equals the conversation's judgment. Paragraph-anchor links back every citation |
| **Steps touched** | Remember, Rewrite, Decide, Cache (key includes `record_id`), Search (exact filter), Re-rank, Gate, Answer, Verify, Show, Save |
| **Tests that try to break it** | question about another case while pinned (not found in this judgment, no answer from memory); cache key collision between two judgments; model cites another judgment → fails; judgment too long for the model → "too long, answering from the most relevant parts" with the parts listed (UX-COPY; longest judgments **not measured**); party/judge names must not appear in answer or header (fields unreliable, CLAUDE.md §6; the judgment *text* contains them, see Owner decisions); anchors resolve; **second frozen test set for talk-with-judgment** |
| **Size** | **S-M** |
| **Switch gate** | Answers pass the verifier against that judgment's own paragraphs |
| **Needs real data / money** | Real `kanoon_v1` with `record_id` payload index and paragraph anchors; Supreme Court text only. Longest-judgment measurement |

---

## 7. Free public Act + statistics pages (indexable), share cards

| | |
|---|---|
| **Lanes** | web (server rendering, sitemap, cards), platform (public routes, cache headers, CDN rules), core (nothing) |
| **Adds (API)** | present: `GET /acts/{act}/sections/{n}`, `GET /stats`; add `GET /acts` (index, **backed by the coverage table, feature 11**), `GET /stats/{court}/{year}`, sitemap data feed; ETag and Cache-Control for CloudFront |
| **Adds (web)** | `/acts/[act]` (sections), `/acts/[act]/[section]` (exists), `/stats/[court]/[year]`, `app/sitemap.ts`, `app/robots.ts`, `generateMetadata`, `opengraph-image` routes, `ShareCard` |
| **Fakes** | existing fake client data; fake sitemap source |
| **Verifier / gate** | **No model writes anything.** Pages show stored dataset text and counts only. Tests: page components import no LLM/adapters; every page carries the data-as-of date, the CC BY credit and the not-legal-advice notice; the share card carries the same three; statistics are descriptive counts only (no %, "chance", prediction; asserted today in `web/src/__tests__/screens.test.tsx`); only rows with `is_final_outcome` true (TECH-STACK-v2 §4) |
| **Steps touched** | None of the 11 |
| **Tests that try to break it** | Act with empty `act_status` shows "in-force status not checked", never an in-force flag; no judge, party or advocate name in rendered HTML (scan test over output); **a lookup that finds nothing says "not in our dataset" (owner wording) with a link to the coverage page and never "does not exist"; the HTTP status is a real 404** (today unknown pages stream the not-found screen with HTTP 200, a soft 404; TECH-STACK-v2 plans the Next.js 16.4.3 upgrade as its own change, whether it fixes this is **unverified**); sitemap lists only pages that exist; huge Act paginates; stats for a court that is not live say "not live", never zeros |
| **Size** | **M** |
| **Switch gate** | Acts: none. **Statistics: Launch-switch, only after the 50-judgment Supreme Court hand check passes** (pass rule to agree with the advocate *before* checking); no advocate named |
| **Needs real data / money** | Real `act_sections` and `cases` tables loaded; the hand check; CloudFront + WAF quotes; domain only after the trademark search (O8); Search Console. `act_status` is filled for 1,568 of 22,264 **acts** (CLAUDE.md §6) and 74,484 **points** (PRD-v2 §3, two different units), so most Act pages say "not checked". Search indexing takes weeks |

---

## 8. Chambers team accounts

| | |
|---|---|
| **Lanes** | platform (orgs, memberships, invites, seats), web (org admin pages), trust (privacy tests) |
| **Adds (API)** | implement `POST /organisations`, `POST/DELETE /organisations/{id}/members` (stubs today, `api/routes/misc.py:55-67`); `GET /organisations/{id}`; `POST /organisations/{id}/invites/accept` |
| **Adds (files)** | `core/orgs.py`; `adapters/email.py` (**Amazon SES, Mumbai**; one file, no other file imports the vendor library) + `FakeEmail`; `migrations/0011_org_invites.py`; web `/org`, `/org/members` |
| **Fakes** | `FakeEmail`, `FakePayments` seats, fake Firebase identities |
| **Verifier / gate** | No model text. The key property is **privacy**: v1 Chambers shares one bill only; each member's chats and uploads stay private (PRD-v2 §4.2). Proof is a test matrix |
| **Steps touched** | Usage check (per user or pooled: owner), step 11 (chat saved under the member, never the org) |
| **Tests that try to break it** | org admin reads a member's conversation, message, upload, export (all fail); admin removes a member (member keeps personal data, seat and bill update); invite to an existing user; invite accepted twice; seats below the configured minimum rejected (**the minimum is a config value**, PRD says 3 as a hypothesis); downgrade below seats; owner deletes account while the org is active; admin actions audited with a reason; unique membership |
| **Size** | **M-L** (seat billing depends on feature 1) |
| **Switch gate** | Minimum seats; **counsel on the processor role** |
| **Needs real data / money** | Feature 1 live; SES production access (the sandbox limits sending: **Needs verification** in Mumbai); owner decisions on pooled versus per-user limits and the owner-leaves case |

---

## 9. Offline reading and resumable uploads (installable web app)

| | |
|---|---|
| **Lanes** | web (service worker, manifest, offline store), platform (resumable upload endpoints), trust (cache privacy review) |
| **Adds (API)** | resumable upload on `POST /documents/uploads` (multipart parts to S3 through pre-signed part URLs: `POST /documents/uploads/{id}/parts`, `.../complete`), behind `FEATURE_UPLOADS` and all upload hardening |
| **Adds (web)** | `public/manifest.webmanifest`, service worker (**unverified** which approach works with `cacheComponents` on Next.js 16.4.x), `OfflineStore` (IndexedDB) for **saved answers** (feature 12), "Saved for offline", upload progress + resume UI, **page-weight and load-time budgets** tested on a throttled connection (numbers set after the interviews) |
| **Fakes** | fake S3 multipart; service worker tests with a fake cache; network toggle in tests |
| **Verifier / gate** | No new model text. A saved answer is stored **exactly as the sealed `citations` event delivered it**, with its data-as-of date, shown read-only; citations are never re-rendered from anything else. Offline never shows a tick for a state it cannot check; it shows "saved on <date>" |
| **Steps touched** | Show (read-only replay) and Save only |
| **Tests that try to break it** | the service worker never caches `Authorization` responses or `/api` answers except an explicit user save; sign-out clears the offline store; two users on one device don't see each other's saves; resume after the tab closes mid-part; resume with a changed file (checksum mismatch → restart); part replay; storage quota exceeded; stale snapshot version (page shows the saved data-as-of); offline Act page keeps "in-force status not checked"; page-weight budget |
| **Size** | **L** |
| **Switch gate** | Page-weight budget tested on a throttled connection |
| **Needs real data / money** | S3 multipart on a real bucket; whether chats may be kept on a device (client confidentiality, owner); icons and brand assets only after the trademark search (O8); HTTPS domain |

---

## 10. Counter-arguments, moot court, study buddy (after the launch gate)

**Orchestration choice is recorded first:** `docs/DECISIONS.md` **A41** (*proposed*): plain
Python fixed sub-pipelines with explicit branches in `core/features/`, no framework; the
runner (not a model) chooses the next branch; the verifier and gate run in the runner after
every model-written block. Ruled out: a framework agent loop where the model picks its next
tool (it cannot guarantee the verifier is never skipped). The owner allowed orchestration for
these features (O4) but the choice is recorded **before** any build (CLAUDE.md §7).

| | Counter-arguments | Moot court | Study buddy |
|---|---|---|---|
| **Lanes** | core, trust, web | core, trust, web | core, trust, web |
| **Adds (API)** | `POST /counter`, `GET /counter/{id}` | `POST /moots`, `POST /moots/{id}/turns`, `GET /moots/{id}` | `POST /study/sessions`, `POST /study/sessions/{id}/answers`, `GET /study/sessions/{id}` |
| **Adds (files)** | `core/features/counter.py`: research the user's position, a second search for the **opposite** side, write, verify | `core/features/moot.py`: `opening → question → reply → score` | `core/features/study.py`: questions built **from gated passages**, each stores its source |
| **Fakes** | `FakeLLM`, `FakeVectorStore` with paired for/against passages | scripted turns | `FakeLLM`, 10 sample passages |
| **Verifier / gate** | each argument sentence cites an `[S#]` from the gate; check 4 asks whether the passage supports *this side's* sentence | any statement of law cites a gated passage and passes checks 1-4; role-play lines with no legal claim are labelled so; the "judge" is **fictional** and never uses a real judge's name | question and answer are tied to one passage; items whose citation fails are dropped |
| **Steps touched** | Rewrite, Decide, Search ×2, Re-rank, Gate ×2, Answer, Verify, Show, Save | Remember, Rewrite, Search, Re-rank, Gate, Answer, Verify, Show, Save | Search, Re-rank, Gate, Answer, Verify, Show, Save |
| **Break tests** | flipped side cites a case supporting the *other* side (check 4 rejects); invented "contrary authority" (check 1); no counter-authority found → says so | injection in the user's reply; model names a real judge (output scan); a turn with no verifiable support has no tick | failed-citation item dropped; blank answer; limits enforced; cache never serves another user's quiz |
| **Size** | M | L | M |
| **Needs** | retrieval quality measured on its own (precision/recall at 10 and 50, PRD-v2 §5.5), Gemini cost per session | same + role-play disclaimer wording (owner) | same; the plan that includes it is a config value |

---

## 11. Coverage page (new, O7)

Purpose: say **exactly what the dataset holds** and nothing more. The owner has only what is on
her drive and believes many Acts may be missing, so the page is built from a measurement, not
from a promise. A failed lookup says "not in our dataset", never "does not exist".

| | |
|---|---|
| **Lanes** | core (the measuring script in `data/`, reads the same source as the build), platform (tables, routes), web (page) |
| **Data source** | **Measured counts only**, produced by `data/coverage_report.py` (new) from (a) the legislation parquet files (37 of the 75 files, Dataset card) and (b) the collection that is actually served (`CORPUS_COLLECTION`). It writes two tables and stamps the run (snapshot version, data-as-of date, script version, run time). It never writes a hand-typed row. Categories are *derived*: jurisdiction and instrument type come from the data's own fields, so a category the data does not hold cannot appear |
| **Tables** | `coverage_acts` (`act_slug`, `act_name`, `act_year`, `jurisdiction`, `instrument_type`, `regulator` if present in the data, `section_count`, `act_status_checked`), `coverage_summary` (counts by jurisdiction × instrument type), and the existing `court_coverage` (`court`, `snapshot_version`, `data_as_of`, `points`, `live`, `stats_live`, `docs/DATA-MODEL.md`). Migration `0012_coverage.py` |
| **API route** | `GET /coverage` (public, no login: summary, courts covered, data-as-of, snapshot version, credit, notice); `GET /coverage/acts?jurisdiction=&instrument_type=&q=&cursor=` (paginated list of every Act with its section count; also powers the `/acts` index and the sitemap, feature 7). Cached by CloudFront |
| **Web** | `/coverage` (server-rendered, indexable): summary table, courts covered with their `live`/`stats_live` status, searchable Act list, the data-as-of date, the CC BY credit and the not-legal-advice notice. Shared `CoverageTable`, `Label`, `Card`; tokens only. Linked from every "not in our dataset" message, from the out-of-scope message and from the footer |
| **Fakes** | a fake coverage table of 6 **sample** rows (labelled "Sample"); a fake with a *missing* category (no state Acts) to prove the page and the message do not mention it |
| **Verifier / gate** | **No model text.** The coverage sentence in the out-of-scope and not-found messages is assembled from the table (categories present in the data), not written by a model. Test: the code that builds the message imports no LLM adapter |
| **Steps touched** | Step 3 Decide (the scope check's out-of-scope message names only measured categories), step 7 (the "not found" message links to the page). Act lookup (payload filter) is not a pipeline step |
| **Tests that try to break it** | the page lists exactly the rows of `coverage_acts` (add or remove a row, the page changes); **no Act, jurisdiction or regulator name hard-coded in `web/` or `api/`** (grep test); the coverage sentence built from a table with no state Acts must not contain "state"; a lookup for an Act that is not in the table returns the "not in our dataset" state with a 404 status and never the words "does not exist" (asserted on the rendered text); counts **reconcile**: sum of `section_count` for a scope equals the rows loaded into `act_sections` for that scope, and the script fails (exit non-zero) if the copy and the parquet disagree (this is how the unexplained **308-point gap** between Qdrant and parquet gets surfaced instead of hidden); a category with zero rows is not listed; unmeasured values display "not measured", never zero; the data-as-of date is present; the script is read-only (opens no write connection to Qdrant) |
| **Size** | **M** |
| **Switch gate** | Built from measured counts only; no category listed that the data does not hold (PRD-v2 §4.2) |
| **Needs real data / money** | The measurement itself (**not done yet**): count Acts by jurisdiction and instrument type from the legislation parquet and from `acts_india`, and explain the 308-point gap (PRD-v2 §3 row 7). The working copy so far takes only 74,509 Central Act points (about 7% of the 1,098,577 `acts_india` points); whether to copy the rest is a second job needing the owner's go (about 15 GB read from the slow drive, Estimate). **The coverage sentence is the owner's wording**; the suggested shape in PRD-v2 §10 is for approval, not used as is |

Until this feature is built and the count exists, **no coverage message is changed in either
direction** (PRD-v2 §3 row 7). The current messages are listed in the Job 3 report.

---

## 12. Saved answers, folders, notes; export an answer to Word or PDF (new)

| | |
|---|---|
| **Lanes** | platform (tables, routes, export job), core (export builder), web (saved list, folders, notes, export button), trust (export boundary) |
| **Adds (API)** | `POST /saved` (save a message), `GET/PATCH/DELETE /saved/{id}`, `GET/POST /folders`, `PATCH/DELETE /folders/{id}`, `GET/POST /saved/{id}/notes`, `POST /exports` (message or draft → docx/pdf), `GET /exports/{id}` |
| **Adds (files)** | `core/saved.py`, `core/export_doc.py` (`python-docx` for Word; PDF from a server-side HTML-to-PDF library with ARM builds, **library not chosen, ARM check is Needs verification**, TECH-STACK-v2 §1); `migrations/0013_saved.py` (`folders`, `saved_items`, `notes`, `exports`); web `/saved`, `FolderTree`, `EmptyState` |
| **Fakes** | `FakeDocxExporter`/`FakePdfExporter` (deterministic bytes), a fake store with sealed messages |
| **Verifier / gate** | **Export is not generative.** It builds from the stored message and its `message_sources`; the citation string is **copied exactly as recorded** and never re-typed by a model (TECH-STACK-v2 §4). It refuses a message whose sources are not `verified`/`partly`/`unchecked` as stored, and puts the same per-citation mark, data-as-of date, CC BY credit and not-legal-advice notice into the file. Notes are the user's own text: never ticked, labelled as the user's |
| **Steps touched** | Step 11 (what was saved) and step 10 formatting rules reused; none of 1-9 |
| **Tests that try to break it** | change a stored citation string then export (the export must show what was recorded, or refuse if integrity fails); an answer with a removed citation exports without it and with the removal note; note text containing `[S1]` must not render as a citation; export of another user's message fails; huge answer; docx/pdf contain the data-as-of date and credit; folder cycles, delete folder keeps or deletes items as the owner decides; account delete (feature 2) removes saved items, folders, notes and exports |
| **Size** | **M** |
| **Switch gate** | The citation string is copied exactly as recorded |
| **Needs real data / money** | PDF library choice and ARM build; nothing else. Export wording (headers, notice placement) is owner wording |

---

## 13. Onboarding, empty states, help centre, support inbox (new)

| | |
|---|---|
| **Lanes** | web (screens), platform (support route, email) |
| **Adds (API)** | `POST /support` (stores `support_messages` or sends through SES to the inbox, per TECH-STACK-v2 §6), `GET /help` index (static content) |
| **Adds (files)** | `adapters/email.py` (shared); `migrations/0014_support.py`; web `/help`, `/help/[slug]`, first-run tips, `EmptyState` on chat / saved / drafts; in-app help form |
| **Fakes** | `FakeEmail`; sample help articles labelled "Sample" |
| **Verifier / gate** | No model text. Help articles are static content written by people. Test: the help and support modules import no LLM adapter; no help text promises more than the product does (checked by the owner, not by code) |
| **Steps touched** | None |
| **Tests that try to break it** | support form spam (rate limit, bot protection); message body never reaches Langfuse/Sentry; a user cannot read another user's support thread; first-run state survives sign-out/in; keyboard path through onboarding |
| **Size** | **S-M** |
| **Needs real data / money** | The help and onboarding wording (owner); a support person from beta (PRD-v2 §6); first response within 1 business day (free) and the same business day (paid) is a target, not a built feature |

---

## Order and dependencies

Feature numbers follow the owner's order (1 to 10) plus the three PRD-v2 additions. The build
order is **TECH-STACK-v2 §8**, which wins; steps 4 to 8 may be built in parallel on fakes once
step 1 shows the core works on real questions. Mapping:

| TECH-STACK-v2 step | Features here |
|---|---|
| 0 Data copy and checks | prerequisite for 6, 7, 10, 11 (measure first; §0.2) |
| 1 Real hybrid search, five real questions | prerequisite for everything below |
| 3 Production foundation (AWS, staging, backups, monitoring, secrets) | prerequisite for going live with any feature |
| 4 Plans, billing, accounts, consents, delete/export, feedback, admin | 1, 2, 3 (+ 8 after 1) |
| 5 Judgment reader, talk with a judgment, saved answers, export | 6, 12 |
| 6 Public pages, share cards, statistics | 7, **11** (coverage feeds the Act index, so build 11 first or together) |
| 7 Upload and chat with full hardening | upload part of 5 and 9 |
| 8 Drafting, review and compare | 4, 5 |
| 9 Private beta, run the launch gate | all Launch / Launch-switch features |
| 10 Branching features, Hindi, High Courts | 10 only (Hindi and High Courts are not planned here) |

Other dependencies: **2 needs 1** (deletion cancels the subscription); **8 needs 1**;
**9 needs 12** (it saves answers) and the upload hardening; **13 and 8 share** `adapters/email.py`;
**5 reuses** the draft document model and sealed documents from 4.

## Owner decisions needed (every one)

**Decided already (not repeated as questions):** widen v1 (O1), owner pays and agents never buy
(O2), agents may revise the PRD and Tech Stack (O3), orchestration allowed for branching
features (O4), no outcome prediction (O5), serve what the data holds (O7), name LexBharat
(O8), pricing deferred (O10), email vendor SES (TECH-STACK-v2).

**Open in PRD-v2:** O6 High Courts after the gate (default shown); O9 GST included or not.

**Prices and plans (feature 1) — deferred (O10); asked again only when billing goes live**
1. The limit numbers per plan and per feature.
2. Final prices, annual prices, seat minimum (₹199, ₹499, ₹299, 3 seats are hypotheses; the design doc's ₹799 is a labelled sample).
3. GST included or excluded and how invoices are issued (O9; accountant).
4. Proof of student status; refunds; failed-payment grace period; data on downgrade.
5. Chambers: pooled or per-user limits; what happens when the org owner leaves.

**Legal-facing wording (not drafted here; code uses placeholders marked `NEEDS-OWNER`)**
6. **The coverage sentence** and the exact "not in our dataset" sentence (they may name only measured categories, O7).
7. Consent notice text and version document (`legal/`), privacy policy, terms, refund and cancellation policy.
8. Retention periods for every row of `docs/RETENTION.md`; the upload auto-delete default.
9. Account-deletion confirmation and what is kept (invoices).
10. Labels for "template text", "AI-drafted, citations checked", "your text", and every disclaimer on drafts, reviews, moot court, study and export screens.
11. The privilege warning before upload; the report-a-wrong-answer dialog and reasons.
12. Anything about advice and BCI Rule 36 on any new page, share card, email or export.
13. Help centre, onboarding and sign-in wording.

**Product and trust**
14. Drafts: how much uncited model-written prose is allowed (proposed rule in feature 4) and what happens at zero surviving citations.
15. Whether the model may quote judge or party names that appear inside judgment text (feature 6): block, mask, or allow inside quotation marks only.
16. Whether user-typed party names in drafts may be stored and sent to Gemini paid tier.
17. Whether the account export includes upload text.
18. Whether saved answers may live on a device offline (client confidentiality).
19. Who the admins are, and whether admins may read reported chat content (logged with a reason).
20. **Confirm A41** (orchestration, feature 10), **A45** (feature-flag table, admin audit shape) and the sealed `VerifiedDocument` design in 0.1.
21. Template list: keep, rename or replace the 20 names; which plan includes each (a config value).
22. Folder delete behaviour (feature 12).

## Costs (every one)

PRD-v2 §6 is the buy list. This table only says which feature needs which item. **No monthly
total is stated** (TECH-STACK-v2 §9: the single-box figure no longer applies; quotes are
needed).

| Cost | Feature | Status |
|---|---|---|
| Razorpay business account and per-transaction fee | 1, 8 | Fee "about 2%" is the PRD's, **Needs verification** |
| Accountant: GST registration and invoice rules | 1 | Get a quote |
| Amazon SES (Mumbai) and the product's own domain for mail | 1, 2, 8, 13 | Sandbox limits **Needs verification**; get a quote |
| Gemini paid-tier calls per draft, review, support lookup, moot turn, study item, counter-argument | 4, 5, 6, 10 | Not measured; key tier not verified (A36) |
| Voyage embeddings for queries and uploaded drafts | 5, 6, 10 | About ₹0.05 per answer is an **Estimate**; written no-training terms needed before uploads |
| Jev decisions per answer (about ₹0.03, **Estimate**) | 6, 10 (law side only) | Never on upload text |
| OCR and ClamAV virus scan on the worker server | 5, 9 | ClamAV on ARM and memory: **Needs verification** |
| Managed PostgreSQL (RDS), CloudFront + WAF, staging server, worker server | all | Get quotes (TECH-STACK-v2 §2) |
| Monitoring, uptime check, status page, phone alerts | all | Vendors undecided; get quotes |
| S3 storage and multipart requests | 2, 5, 9, 12 | Small; not estimated |
| Firebase Auth (second factor for admin) | 2, 3, 8 | Limits **unverified** |
| Counsel: consent notice, privacy policy, terms, retention, refund policy | 1, 2, 8 | Required before launch; get a quote |
| Advocate advisor: templates, review checklists, knowledge notes, test sets, wrong-answer reports | 3, 4, 5, 6 | Retainer; get a quote |
| Independent security test | all | After feature freeze; get quotes |
| Trademark search and filing (IP India) before domain, logo or brand spend | 7, 9 | Get a quote (O8) |
| Editor library licence (e.g. TipTap extensions), Word and PDF export libraries | 4, 5, 12 | **Unverified** |
| Part-time support person | 13 | From beta; get a quote |

## What this plan did not verify

- **Nothing was built or run.** No test, lint or build was executed for this document.
- Sizes are guesses. No cost number is measured. The data facts in §0.2 and feature 11 are
  **Reported** by the data session, not re-run here; the Qdrant copy was not touched.
- Razorpay subscriptions, UPI autopay and GST invoices; Firebase admin deletion and
  multi-factor; SES limits in Mumbai; ClamAV on ARM; Next.js service-worker and soft-404
  behaviour on 16.4.x; TipTap licensing; PDF library ARM builds were **not** checked against
  current vendor documentation.
- The mechanical detection of "a sentence that states what the law is" (feature 4) relies on a
  heuristic whose recall on real drafts is unknown.
- Statements about the existing code come from reading `api/routes/*.py`, `adapters/razorpay.py`,
  `core/verify.py`, `core/contracts.py` and `docs/*` today.
