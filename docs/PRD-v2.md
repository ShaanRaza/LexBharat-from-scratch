# PRD v2: production-ready v1

**Revision 2, 2 November 2026. Owner: Akshita Johari (founder).**
Replaces the scope, launch gate and open questions of the original PRD
(`KanoonBuddy-Product-Requirements-Document.pdf`, build draft 9 October 2026). Everything
in the original that this file does not change still stands. Where this file and
[`TECH-STACK-v2.md`](TECH-STACK-v2.md) disagree, **the Tech Stack wins**.

Evidence labels are kept, as in the original: **Measured**, **Checked**, **Dataset card**,
**Competitor claim**, **Estimate**, **Needs verification**. New label: **Reported** =
measured by another working session and written down, not re-run by the author of this
file. Nothing here promotes an Estimate to a fact.

---

## 1. What changed, in plain words

1. **v1 is widened.** The original PRD launched a thin core (research chat, Act lookup,
   upload) and pushed drafting, review, statistics and most business features to later.
   The owner has asked for a production-ready product, so those move into v1.
2. **Production basics are added.** The original had almost nothing on staging,
   monitoring, backups you have actually restored, abuse protection, emails, GST invoices,
   refunds, terms and privacy documents, or support. Section 5 adds them.
3. **The trust promise does not move.** Every feature that writes legal text goes through
   the same verifier and gate. The launch gate gets longer, not shorter (section 7).
4. **Some PRD facts were wrong or have changed.** Section 3 lists them.

## 2. Owner decisions recorded here

| # | Decision | Date | Status |
|---|---|---|---|
| O1 | Widen v1 to a production-ready product (section 4) | 2 Nov 2026 | **Decided** |
| O2 | The owner pays for the services and people in section 6. Agents never buy anything and never print or commit a key; the owner creates the accounts and puts keys in `.env` / Secrets Manager | 2 Nov 2026 | **Decided** (each purchase still needs the owner to do it) |
| O3 | Agents may revise the PRD and the Tech Stack; every revision is recorded and the original PDFs are kept | 2 Nov 2026 | **Decided** (this file is the first revision) |
| O4 | Orchestration inside the product is allowed for branching features only, with the verifier and gate always running afterwards, outside the agents' control | 1 Nov 2026 | **Decided** (see CLAUDE.md section 7) |
| O5 | Outcome **prediction** is not built. Outcome statistics stay descriptive counts | 2 Nov 2026 | **Decided** (CLAUDE.md hard rule; the original PRD said "ship with warnings, or skip") |
| O6 | High Courts: add Bombay, Telangana, Kerala after the Supreme Court side passes the launch gate. Data preparation may start now | proposed | **Open** (owner to confirm; default shown) |
| O7 | Acts coverage: serve **all of `acts_india`** (about 22,264 acts, 1,098,577 points) or only acts with `act_status` filled (about 74,509 points, 1,568 acts) | | **Open, important.** See section 3, row 7 |
| O8 | Final product name | | Open (trademark search first; the PRD recommends Praman) |
| O9 | GST: prices shown with or without GST | | Open (accountant) |

## 3. Facts in the original PRD that are wrong, changed or newly known

| # | Original PRD said | Now | Label |
|---|---|---|---|
| 1 | Keyword (BM25) search must be built from scratch because the dataset lists only dense vectors | The Supreme Court points already carry BM25 sparse vectors made with FastEmbed `Qdrant/bm25`; 16 of 16 sampled reproduce exactly. Queries must be encoded with `query_embed()`, not `embed()` | Reported |
| 2 | About 2 to 3 million Supreme Court points | English Supreme Court chunks: **371,247** in the parquet files, **371,159** in `legal_corpus_v2`. A further roughly 742,000 translated chunks exist in the files and are **not embedded** | Reported |
| 3 | Every stored vector was made with voyage-4 | Mixed. A judgment chunk matches voyage-4 exactly; one Central Act chunk matches **voyage-4-large**. One chunk each was tested; more testing is pending | Reported |
| 4 | Court field name unknown | Select English Supreme Court with `court = "Supreme Court of India"`. `language_code` is mostly empty and uses upper-case `EN`; do not filter on it | Reported |
| 5 | Keyword search works on all `acts_india` points | **19,835 of 74,509** Central Act points (26.6%) have sparse vectors that do not match the encoder, so keyword search silently misses them. A repair script exists (`data/sparse_fix.py`) and has **not** been run on live data | Measured (full scan of those points), reported |
| 6 | Gemini 2.5 Flash-Lite for the free plan | Retired for new accounts. Config now uses `gemini/gemini-3.5-flash-lite` (decision A36). Model names stay in config | Checked live, 2 Nov 2026 |
| 7 | v1 serves `acts_india` (22,264 acts) and the failure message says "central and state Acts and regulations" | The repo's data copy plan takes **74,509 Central Act points**, which almost equals the **74,484** rows with `act_status` filled. That is about 7% of the 1,098,577 `acts_india` points. Either the narrowing was deliberate or the copy leaves out state Acts and regulators that the PRD counts as v1. The 308-point gap between Qdrant and parquet is also unexplained | **Needs verification** (decision O7). Until settled, do not change the coverage message in either direction |
| 8 | Server needs 42 to 55 GB of vectors | Recalculated from item 2: about (371,159 + up to 1,098,577) points x about 13.5 KB is roughly **20 GB** of disk and about **1.5 to 2 GB** of memory with scalar quantization if all of `acts_india` is served | Estimate (PRD's own per-point rule applied to the reported counts) |
| 9 | Failure state "the retrieved sources are shown with links but no written answer" | Not yet built: the API sends only an error event. See UX-COPY and decision A40 | Open |

## 4. Scope of v1 (replaces the PRD's MVP scope table)

Priority key: **Launch** = built and switched on at public launch. **Launch-switch** =
built before launch; switched on only when its own gate (right-hand column) passes.
**After launch** = built after the launch gate passes. **Not building** = a decision.

### 4.1 Core (unchanged from the original, still the first thing to prove)

| Feature | Priority | Notes |
|---|---|---|
| Research chat with verified citations (11-step pipeline) | Launch | Passage counts stay 50 to 10 to at most 8 |
| Supreme Court judgments | Launch | |
| Act and section lookup, free and public | Launch | In-force flag shown only where `act_status` is filled; otherwise "in-force status not checked" |
| Citation verifier (four checks), invented-citation log | Launch | Never weakened |
| Decision layer (Jev) with Gemini fallback | Launch | Each use has its own switch; turned on one at a time after a live comparison |
| Knowledge notes (IPC to BNS, CrPC to BNSS, Evidence Act to BSA, limitation, coverage) | Launch | Only advocate-reviewed notes reach live answers |
| Answer cache, usage meter, source credit, data-as-of date | Launch | |

### 4.2 Widened into v1

| Feature | Priority | Gate to switch on |
|---|---|---|
| Plans, pricing page, Razorpay subscriptions, visible monthly limits | Launch | GST decision (O9); refund policy; test-mode run end to end |
| Account: sign-in, consent notice with version, delete account, export my data | Launch | Counsel decides what `DELETE /me` keeps (invoices) |
| Rating, "report a wrong answer", admin page (triage, 200-question runner) | Launch | |
| Free public Act pages and Supreme Court outcome-statistics pages, share cards | Launch (statistics: Launch-switch) | **50-judgment Supreme Court hand check passes**; no advocate named; descriptive counts only |
| Chambers team accounts (shared bill, each member's chats private) | Launch | Minimum 3 seats; counsel on processor role |
| Judgment reader with paragraph anchors | Launch | Backs every citation link |
| **Talk with a single judgment** (summary, issues, ratio) | Launch | Answers pass the verifier against that judgment's own paragraphs |
| **Saved answers, folders and notes** (new) | Launch | Lawyers keep research for weeks |
| **Export an answer to Word or PDF with citations intact** (new) | Launch | The citation string is copied exactly as recorded |
| **Onboarding, empty states, help centre, support inbox** (new) | Launch | |
| Upload and chat (OCR, per-user isolation, hard delete) | Launch-switch | Advocate's written opinion; Voyage's written no-training and retention terms; interviews show advocates would upload; virus scan and injection tests pass |
| **Drafting from templates** (first list of 20) | Launch-switch | Template wording written or signed off by the advocate advisor; drafts that cite law go through the verifier |
| **Review and compare drafts** | Launch-switch | Risk review flags are labelled as information, not advice; advocate samples 20 outputs |
| Offline reading of saved answers, resumable uploads (installable web app) | Launch | Page-weight budget tested on a throttled connection |

### 4.3 After the launch gate

| Feature | Priority | Notes |
|---|---|---|
| Counter-arguments, moot court, study buddy | After launch | Branching features: orchestration allowed (O4); decision recorded in `docs/DECISIONS.md` before any build |
| Hindi | After launch | Only after the PRD's tests pass: voyage-4 on 30 Hindi questions, a Hindi-aware keyword tokenizer, 20 answers checked by an advocate |
| High Courts: Bombay, Telangana, Kerala | After launch | Needs: points counted per court, payload indexes, 577-value disposition cleaning plus its own 50-judgment check, junk-field check, server resize. High Court answers show **no citation string** (0.0% filled) |
| "Is this still good law?" signal (a citator) | Research item | The tick does **not** mean good law and the dataset has no overruled/followed data. This is the largest gap against Manupatra and SCC Online. Do not promise it; first work out whether it can be derived from the judgments' own text |
| Data refresh pipeline | Backlog (decision D2) | The owner may reopen this. Until then every page shows the data-as-of date |
| Tribunals | Later | OCR cost, not licensing. Not advertised at launch |
| Shared team workspace | Month 6 onward | |

### 4.4 Not building

- Outcome prediction or "win chances" (O5).
- Any listing, ranking, matching or recommending of advocates, or "find a lawyer" (BCI Rule 36).
- Court tracking, e-filing, a practice-management suite (original non-goals stand).
- A native mobile app (the installable web app is the plan).

## 5. New requirements the original PRD did not have

These are product requirements. The how is in [`TECH-STACK-v2.md`](TECH-STACK-v2.md).

### 5.1 Running it for real

| Area | Requirement |
|---|---|
| Environments | Development, **staging**, production. Nothing reaches production without passing staging first |
| Releases | Every release runs the test suite, the trust tests and the 200-question set. A bad release can be rolled back in minutes. Database changes are reversible |
| Monitoring | Alerts for downtime, error spikes, slow answers, a failed backup, a payment webhook failing, a full disk. Alerts reach the owner's phone, not only an inbox |
| Status page | A public page that shows whether the product is up |
| Backups | Daily. A **restore drill** (rebuild from backups on a clean machine) is done and timed before launch and repeated every quarter. Target: rebuild under 1 hour (Estimate) |
| Capacity | A load test at an agreed number of simultaneous users; the number is set from beta data (Needs verification) |
| Cost control | A daily cost per answer view; a hard stop if daily AI spend passes a set limit |

### 5.2 Safety and abuse

| Area | Requirement |
|---|---|
| Abuse protection | Rate limits per user and per address, bot protection on sign-up and public pages, a firewall in front of the site |
| Prompt injection | Uploaded files and retrieved judgment text are treated as data, never as instructions. A fixed attack test set runs on every release: no answer may skip the verifier, reveal another user's data, or follow an instruction found inside a document |
| Uploads | File type and size checks, page limit, virus scan, a sandboxed reader, no network access from the reader |
| Admin | Sign-in with a second factor; every admin view of user data is logged with a reason |
| Third parties | A list of every vendor, what it receives and where, kept current on the privacy page (the Tech Stack's "Where data goes" table is the start) |

### 5.3 Legal and customer documents (owner arranges; counsel reviews)

Terms of service; privacy policy; DPDP consent notice and retention periods; a named
contact for privacy questions and grievances (exact duty: Needs counsel); refund and
cancellation policy; GST invoices; a takedown process for judgments (the dataset card names
a redaction contact); a policy for answering legal orders; a breach playbook (exists in the
repo, to be rehearsed once); wording on privilege before upload.

### 5.4 Customer experience

| Area | Requirement |
|---|---|
| Billing | Failed-payment handling, plan change, cancellation, receipts by email, GST invoice on every payment (Needs verification: whether Razorpay's subscription invoices meet GST rules; accountant decides) |
| Email | Sign-up confirmation, password reset, receipts, usage warnings. Sent from the product's own domain, with working unsubscribe for non-essential mail |
| Support | Help centre, support email and in-app form; first response within 1 business day (free) and the same business day (paid) during beta, as in the original |
| Accessibility | Core flows (ask, read an answer, open a citation, pay) work with a keyboard and a screen reader. Target WCAG 2.2 AA (a proposed target, not yet decided) |
| Analytics | Product events logged in our own database. **Never** document text, questions' content or party names. No third-party analytics scripts at launch |
| Performance | Page-weight and load-time budgets per page, tested on a throttled connection (numbers set after the interviews) |

### 5.5 Quality

| Area | Requirement |
|---|---|
| Test set | The 200-question set (100 real, 50 Act lookups, 50 traps) signed off by the advocate and frozen. A **second** frozen set for each new feature (drafting, talk-with-judgment, review) |
| Correctness | Two advocates grade a sample blind; a third settles disagreements (original PRD) |
| Verifier accuracy | A random sample of "verified" citations checked by hand every release |
| Retrieval | Search quality is measured on its own (precision and recall at 10, 50), separately from answer quality. The original plan had no retrieval metric |

## 6. What must be bought or arranged

Prices are not quoted unless a source is named. **Get quotes before spending.**

| Item | When | Cost status |
|---|---|---|
| AWS account: servers in Mumbai, S3, KMS, Secrets Manager, managed database, CDN and firewall | Before staging | Server prices in the original PRD and Tech Stack (r7g.large $0.0751 an hour, r7g.xlarge $0.150 an hour) are their figures; managed database, firewall and CDN: **get quotes** |
| Voyage account on a paid plan, with **written** no-training and retention terms | Before any upload or real traffic | Prices Checked in the original; whether the 200M free tokens recur is **Needs verification** |
| Gemini paid tier (billing switched on, confirmed in Google AI Studio) | Now | Prices in the Tech Stack are Checked there |
| Jev (TypeSafe) credits and **written** terms | Now | $5 bought; terms: email TypeSafe |
| Razorpay business account (KYC takes time) | Start now | Fee about 2% (Needs verification) |
| Email sending service, uptime monitoring, status page, error and AI-trace monitoring | Before staging | Get quotes |
| Domain, logo, brand work | **Only after** the name is final and the trademark search is done | Get quotes |
| Trademark search and filing (IP India) | Now | Get quote |
| Advocate's written opinion (privilege, DPDP roles, the advice line, BCI Rule 36, naming an advisor on the site) | Now (slow) | Get quote |
| Lawyer for terms, privacy policy, DPDP notice, refund policy | Before launch | Get quote |
| Independent security test | After feature freeze, before launch | Get quotes |
| Accountant: GST registration and invoice rules | Before billing goes live | Get quote |
| Advocate advisor retainer (review of knowledge notes, templates, test set, wrong-answer reports) | Now | Get quote |
| Part-time support person | From beta | Get quote |
| Vaquill: email the three questions (licence for caching and public pages; bulk or daily-sync cost; judgments endpoint on the roadmap) | Now (free) | None |

**Do not buy yet:** High Court or tribunal servers (O6), a second production server
(trigger in the Tech Stack), brand spend (O8).

## 7. Launch gate v2 (replaces the original gate)

Public launch happens only if **all** are true at the end of the private beta. If any fails,
the launch date moves; the owner decides.

**Trust (from the original):**
1. Verified-citation rate 98% or higher on the 200-question set.
2. Zero confirmed fabricated citations reaching a beta user; removed-citation rate under 0.5% (Estimate).
3. The advocate's written opinion received.
4. Voyage's written no-training and retention terms received.
5. Independent security test passed.
6. Data-as-of date shown prominently on every result, statistics page and Act page.
7. At least 6 of 10 beta advocates say they would pay the Pro price.

**New for production:**
8. Restore drill passed within the target, using backups only.
9. A release rehearsed on staging, including a rollback.
10. Alerts reach the owner's phone; the status page and uptime check are live.
11. Terms, privacy policy, DPDP notice, refund policy published; counsel has read them.
12. GST invoices tested in Razorpay test mode and accepted by the accountant.
13. The prompt-injection test set passes on research chat, uploads and every feature that writes legal text.
14. A load test at the agreed number passes the speed targets.
15. Core flows pass the keyboard and screen-reader check.
16. Every Launch-switch feature that is being switched on has passed its own gate (section 4.2). Features that have not stay off.

## 8. Success metrics added

Keep all original metrics. Add: uptime (99.5% a month, Estimate); share of answers slower
than the 20-second target; payment success rate; support first-response time; daily cost
per answer against the plan margin; share of wrong-answer reports confirmed by the advocate.

## 9. People

Still one builder directing AI coding agents (original decision). The roles section 6 asks
the owner to arrange: **advocate advisor**, **counsel**, **independent security tester**,
**accountant**, **part-time support**. No timeline is promised; the original PRD's own rule
stands: time build steps 1 and 2, then re-plan.

## 10. Open questions after this revision

Owner decisions O6 to O9 above, and:

- Which of the two coverage statements is true for Acts (row 7 of section 3).
- Wording shown to users, including the two not-legal-advice sentences, the removal note,
  the consent text and the stats and sign-in text (placeholders marked `NEEDS-OWNER`).
- Retention periods and what `DELETE /me` keeps (counsel).
- What `cases.title` holds and whether it may ever be shown.
- The pass rule for the 50-judgment Supreme Court hand check (agree it with the advocate *before* checking).
- Upload size and page limits; upload auto-delete period (advocate's opinion).
- Final prices: ₹199 and ₹499 are hypotheses; the website design doc's ₹799 is a labelled sample.

## 11. Change log

- **2 Nov 2026:** first revision. Widened v1 (O1); recorded owner decisions O1 to O9;
  corrected nine facts (section 3); added production, safety, legal and quality
  requirements (section 5); added the buy list (section 6); replaced the launch gate with
  a 16-point gate (section 7). Original PDFs unchanged.
