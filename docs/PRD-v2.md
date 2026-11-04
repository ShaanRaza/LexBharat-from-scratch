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
| O7 | Acts coverage: **serve what the dataset actually holds, and say exactly what that is.** The owner has only what is on her drive and believes many Acts may be missing. So: (1) measure what is there, by Act, jurisdiction and instrument type; (2) publish that as a coverage page; (3) when a lookup finds nothing, say "not in our dataset", never "does not exist"; (4) the coverage message names only what the measurement shows. Which Acts are in is a measurement, not a promise | 2 Nov 2026 | **Decided** (the measurement itself is still to do; see section 3, row 7) |
| O8 | Product name: **LexBharat** (replaces the working name KanoonBuddy; Praman is dropped). A trademark search with IP India must still be done **before** any domain, logo or brand spend | 2 Nov 2026 | **Decided** (trademark search pending) |
| O9 | GST: prices shown with or without GST | | Open (accountant) |
| O10 | Pricing: decided later. ₹199, ₹499 and ₹299 stay hypotheses. Prices and limits live in config, never in code, so billing can be built and tested with placeholder plans | 2 Nov 2026 | **Deferred by the owner** |
| O11 | **Matters are in v1.** A matter is one case or project. Saved answers, uploads, drafts and remembered facts hang off it. One table; the word shown is "Matter" for advocates and "Project" for students (a label, not a second feature). Every table that holds user work carries a nullable `matter_id` **from its first migration**, even where the screen ships later, so the column never has to be retrofitted | 2 Nov 2026 | **Decided** |
| O12 | **Memory is split in two, because the two halves carry different risk.** (a) *Answer preferences* — how the user wants answers (short, numbered, lead with the conclusion). About the user, no client material, may go to Jev, kept until deleted. (b) *Matter facts* — "I act for the petitioner", "the damages period is 2019-2021". This **is** client material and is treated exactly like upload text: Gemini only (never Jev), masked in Langfuse, scrubbed in Sentry, read only through the shared user-filtered data-access function, hard-deleted with its matter. Nothing is ever remembered automatically: the user presses save, and one page lists every stored item with a delete button | 2 Nov 2026 | **Decided in shape** (the retention clock is O13) |
| O13 | Memory retention: **proposed, owner and counsel confirm.** Matter facts live as long as their matter and die with it or with the account. There is deliberately **no short auto-delete clock**, because Indian litigation runs for years and silently deleting a lawyer's case notes at 12 months would damage the work the product exists to support. Instead: a yearly "is this matter still active?" prompt, and a matter the user archives is hard-deleted 12 months after archiving. Preferences live until deleted | proposed | **Open** (retention periods are the owner's call, CLAUDE.md section 8; counsel reviews the wording) |
| O14 | **Share links are allowed, with one hard limit:** only an answer built purely from the public dataset may be shared. If an upload or a matter fact shaped the answer, sharing is blocked and the user is offered a clean re-run without their own material. Links are unguessable, revocable, expire by default and are never indexed by search engines; the shared page carries the data-as-of date, the CC BY credit and the not-legal-advice notice, and names no advocate (BCI Rule 36) | 2 Nov 2026 | **Decided** (expiry period: owner, with O13) |
| O15 | Practice questions and exam drills for law students: **not in v1.** The owner declined. Revisit only with the study-buddy feature after the gate | 2 Nov 2026 | **Decided (declined)** |

## 3. Facts in the original PRD that are wrong, changed or newly known

| # | Original PRD said | Now | Label |
|---|---|---|---|
| 1 | Keyword (BM25) search must be built from scratch because the dataset lists only dense vectors | The Supreme Court points already carry BM25 sparse vectors made with FastEmbed `Qdrant/bm25`; 16 of 16 sampled reproduce exactly. Queries must be encoded with `query_embed()`, not `embed()` | Reported |
| 2 | About 2 to 3 million Supreme Court points | English Supreme Court chunks: **371,247** in the parquet files, **371,159** in `legal_corpus_v2`. A further roughly 742,000 translated chunks exist in the files and are **not embedded** | Reported |
| 3 | Every stored vector was made with voyage-4 | Mixed. A judgment chunk matches voyage-4 exactly; one Central Act chunk matches **voyage-4-large**. One chunk each was tested; more testing is pending | Reported |
| 4 | Court field name unknown | Select English Supreme Court with `court = "Supreme Court of India"`. `language_code` is mostly empty and uses upper-case `EN`; do not filter on it | Reported |
| 5 | Keyword search works on all `acts_india` points | **19,835 of 74,509** Central Act points (26.6%) have sparse vectors that do not match the encoder, so keyword search silently misses them. A repair script exists (`data/sparse_fix.py`) and has **not** been run on live data | Measured (full scan of those points), reported |
| 6 | Gemini 2.5 Flash-Lite for the free plan | Retired for new accounts. Config now uses `gemini/gemini-3.5-flash-lite` (decision A36). Model names stay in config | Checked live, 2 Nov 2026 |
| 7 | v1 serves `acts_india` (22,264 acts) and the failure message says "central and state Acts and regulations" | The repo's data copy plan takes **74,509 Central Act points**, which almost equals the **74,484** rows with `act_status` filled. That is about 7% of the 1,098,577 `acts_india` points. Either the narrowing was deliberate or the copy leaves out state Acts and regulators that the PRD counts as v1. The 308-point gap between Qdrant and parquet is also unexplained | **Decided (O7): serve what the data holds.** To do: count Acts by jurisdiction and instrument type from the legislation parquet files and from `acts_india`, and explain the 308-point gap. Until that count exists, do not change the coverage message in either direction |
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
| **Matters** (new, O11): a page per case or project holding its saved answers, uploads, drafts, notes and remembered facts. Replaces plain "saved answers and folders" | Launch | One table; label differs for advocates and students. `matter_id` exists on every user-work table from its first migration |
| **Answer view with the source open beside the chat** (new): the judgment or Act section sits next to the answer; clicking a citation jumps to that paragraph | Launch | Reuses the judgment reader with paragraph anchors, already in this table, so most of the cost is wiring, not new work |
| **Live progress panel** (new): named steps as the answer is produced — understanding the question, searching, checking sources, writing, verifying — with counts | Launch | **Step names and counts only.** Never a case name, citation or quote before verification. Pipeline step 10 is unchanged: checked citations still arrive as one final event |
| **Follow-up suggestions, and a Copy / Export / Rewrite row under each answer** (new) | Launch | Follow-ups are questions, never claims, and are produced after verification. Any follow-up the user runs goes through the full pipeline like any other question |
| **"Improve my question" helper** (new): rewrites a rough question into a sharper one | Launch | Lives **in the input box, before the user sends**, and shows editable text. It is not a pipeline step; the 11 steps stay untouched (CLAUDE.md section 4) |
| **History and search across your own saved work** (new) | Launch | PostgreSQL full-text; no new vendor. Always filtered by `user_id` through the shared data-access function |
| **Task cards** (new): one-click read-only jobs — summarise this judgment, timeline of key events, explain this section | Launch | Read-only jobs only at launch. Every timeline row and summary point carries a quoted span that the verifier confirms exists in the record. Drafting-style cards stay in the gated rows below |
| **Share a saved answer by link** (new, O14) | Launch | Blocked for any answer shaped by an upload or a matter fact; revocable; expires; not indexed; carries date, credit and notice; names no advocate |
| **Memory** (new, O12): saved answer preferences, and matter facts saved explicitly to one matter | **Launch-switch** | Switched on only when: one page lists every stored item and deletes it for real; matter facts provably never reach Jev, Langfuse or Sentry; the retention wording (O13) is settled with counsel; the injection and isolation tests cover it |
| **Export an answer to Word or PDF with citations intact** (new) | Launch | The citation string is copied exactly as recorded |
| **Onboarding, empty states, help centre, support inbox** (new) | Launch | |
| **Coverage page** (new): every Act and regulator in the dataset with its section count, which courts are covered, the data-as-of date | Launch | Built from measured counts only; no category listed that the data does not hold (O7) |
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
| **Review tables**: one row per judgment or document, one column per question, exportable | After launch | Every cell is its own small answer and needs its own verified citation, so 20 rows by 5 columns is 100 verifier runs. Cost and speed must be measured before this is promised |
| **Playbooks**: the user's own checklist of rules run against a document, giving accept-or-dismiss suggestions | After launch | Depends on review and compare passing its gate first |

### 4.4 Not building

- Outcome prediction or "win chances" (O5).
- Any listing, ranking, matching or recommending of advocates, or "find a lawyer" (BCI Rule 36).
- Court tracking, e-filing, a practice-management suite (original non-goals stand).
- A native mobile app (the installable web app is the plan).
- Practice questions and exam drills for students (O15, owner declined).
- Word and Outlook add-ins, and connectors to document-management systems. Large to build, larger to maintain, and they serve firms with that software, not the solo advocates and students this product is for.
- Our own trained model. The rule is no training on user data, and a fixed pipeline over a verified dataset does not need one.
- An analytics or benchmarking console for firm leaders, a legal-intake queue, and regulatory horizon scanning. Horizon scanning is impossible anyway on a frozen snapshot with no refresh pipeline (decision D2).
- Editing many documents at once in parallel.

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
| Prompt injection | Uploaded files, retrieved judgment text **and remembered matter facts** are treated as data, never as instructions. A fixed attack test set runs on every release: no answer may skip the verifier, reveal another user's data, or follow an instruction found inside a document or a saved memory |
| Memory and sharing | Tests must show that a matter fact never reaches Jev, Langfuse or Sentry; that one user's memory can never surface in another user's answer; and that a share link cannot be created for an answer shaped by an upload or a matter fact (O12, O14) |
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

## 7. Launch gate v3 (full scope; replaces gate v2, which was written for the MVP)

**Rewritten 4 Nov 2026** after the owner widened v1 to the full product on 3 Nov (`CLAUDE.md`
section 1: every data source the dataset holds). Gate v2's 18 items are all
kept below, unchanged in substance. Items 19 to 34 are new. **Nothing was dropped to make the gate
reachable.** Where an item now looks unachievable as written, that is said in the item and the item
stays in.

Public launch happens only if **all** are true at the end of the private beta. If any fails, the
launch date moves; the owner decides.

### 7.0 Decision that fixes the shape of this gate

**G-T is settled: launch ships WITHOUT tribunals (owner, 4 Nov 2026, A139).** Tribunals are not in the
dataset. Getting them depends on Vaquill, who has not replied, or on extraction from the tribunals'
own published orders that nobody has scoped. Under the alternative nobody the owner controls could
set a date, which is why it was not chosen. Both branches stay below as the record of why.

- **Branch 1, launch waits for tribunals (not taken).** Items 19 to 34 would have applied to
  tribunals as well: their own court-from-id mapping, their own embedding-model row (a tribunal is
  refused by the search until registered, A131), their own eval questions, hand check, latency and
  size measurements. Launch would have had **no date**: "tribunal data held and measured" plus a
  gate pass. The risk was that the date never arrives.
- **Branch 2, launch ships without tribunals (taken).** Tribunals appear in the `excluded` list of
  `core/coverage.json`, which is the single source (A51/O7); the coverage message, coverage page,
  scope check and decide prompt read it and every user-facing sentence follows from it. Tribunals
  are typed nowhere else and no court or instrument name is typed outside that file.
  `tests/test_coverage_source.py` enforces this and passes. The 200-question set keeps its tribunal
  questions as **expected refusals that must pass as correct refusals** (item 25). Nothing in
  marketing, help or pricing may imply tribunal coverage. Tribunals move to "After launch".

**Under Branch 2, every item in 19 to 34 is scoped to the courts and instruments that are served.**
No item requires tribunal data, a tribunal mapping, a tribunal model row or a tribunal measurement,
and none may be read as implying tribunal coverage. Adding tribunals later is a data change plus
re-running items 19 to 34 for them; it is not a code change, because `core/coverage.json` is the
single source. What it would cost is stated where it matters (item 25).

### 7.1 Trust (from the original)

1. Verified-citation rate 98% or higher on the 200-question set, **as extended by item 25**. At the
   time of writing 100 of the 200 rows are stubs with no advocate-labelled expected records (A101),
   so this item cannot be scored at all until they are labelled. A pass with stubs counted out is
   not a pass.
2. Zero confirmed fabricated citations reaching a beta user; removed-citation rate under 0.5% (Estimate).
3. The advocate's written opinion received.
4. Voyage's written no-training and retention terms received.
5. Independent security test passed.
6. Data-as-of date shown prominently on every result, statistics page and Act page.
7. At least 6 of 10 beta advocates say they would pay the Pro price.

### 7.2 Production (from v2)

8. Restore drill passed within the target, using backups only.
9. A release rehearsed on staging, including a rollback.
10. Alerts reach the owner's phone; the status page and uptime check are live.
11. Terms, privacy policy, DPDP notice, refund policy published; counsel has read them.
12. GST invoices tested in Razorpay test mode and accepted by the accountant.
13. The prompt-injection test set passes on research chat, uploads and every feature that writes legal text.
14. A load test at the agreed number passes the speed targets (`CLAUDE.md` section 10), **measured on the real server with the real corpus, per item 27.** Flagged at risk: a single Voyage query embed measured 1,140 ms p50 from a laptop (A131), above the whole 800 ms search-stage target on its own. **The 800 ms search-stage target includes the query embedding (owner, 4 Nov 2026): the user waits for it like everything else.** On the laptop measurement the target is therefore currently unreachable, and that is the finding, not a reason to redefine the target. It may be reachable from the Mumbai server; that is unknown. If it is not reachable on the server either, the item stays and the owner chooses between a different embedding path and a changed target; the target is not edited quietly.
15. Core flows pass the keyboard and screen-reader check.
16. Every Launch-switch feature that is being switched on has passed its own gate (section 4.2). Features that have not stay off.
17. A user can see every item memory has stored about them on one page, edit it and delete it, and the delete is a real delete, checked in the database and in Qdrant (O12).
18. A share link cannot be made for an answer shaped by an upload or a matter fact; an existing link can be revoked and stops working at once (O14).

### 7.3 Full scope (new)

**High Courts (all of them, not three)**

19. **The served collection holds every High Court the dataset holds, and `core/coverage.json` records exactly that. Tribunals are in its excluded list and in no collection (A139).** `core/coverage.json` is now written and measured (A146, 4 Nov 2026): the Supreme Court and 25 High Courts, Central Acts, State Acts and regulations, generated by `data/coverage_report.py`. **What is still required:** it states the launch scope, and `kanoon_v1` today serves the Supreme Court and Central Acts only (455,755 points). Evidence at the gate: point count per court and per `jurisdiction` in the launch collection against the source, with the gap explained (A141 is open: 18.26% of whole cases have no chunk), and a served-court facet that equals the file's `courts`. The coverage page, scope check and every user-facing sentence read the file; none is typed (A51).
20. **`court` is derived from the record id on every served High Court point** (A130); no tribunal mapping is needed or built. `data/add_court_code.py <collection> --apply` has been run on the launch collection (it is **not verified** on a High Court collection yet) and the count of points with no `court_code` is reported. Also required: the rate at which the stored `court` label is wrong, measured on the launch collection (`DATA-GAPS.md` section 15; it is still unmeasured at corpus level), because a wrong label serves one court's law under another's name. The alias table in `core/court_ids.json` is a judgement, not a measurement; the owner or advocate reviews it.
21. **Kerala.** The 217,766 dead dense vectors are served from the repaired copy (A123, staging collection `kerala_v2_fix`), the duplicate rule is applied (A126, A132: one point per `chunk_id`, a dead copy deleted where a live one exists), and Kerala recall is **re-measured after promotion** with the known-item harness (`DATA-GAPS.md` section 17 is the baseline). **Kerala must be within 5 points of the median served court on hybrid @10 (owner, 4 Nov 2026).** Reasoning, recorded so the number is not misread: the measured Kerala gap was on dense, hybrid absorbed it, and A126 means the repaired vectors are never served, so after promotion Kerala should be at parity. Five points is a "something unexpected happened" tripwire, not a tolerance. **A second condition, because the first one cannot fail on its own (owner, 4 Nov 2026): Kerala must also be within 8 points of the median served court on dense @10.** A138 measured that hybrid on this harness sits at its ceiling — 95.8%, moved by exactly 0 of 715 queries — so a hybrid-only tripwire would pass whatever happened to Kerala. Dense is the metric that can actually move, and it is where the original 10–12 point Kerala gap was seen, so **dense is the condition expected to bind**; hybrid stays as the second because a hybrid failure would mean something much worse. The 8-point band is wider than hybrid's 5 because dense moves 1.6–3.5 points from a query-model change alone (A136) and courts differ naturally; it is wide enough not to fire on noise and tight enough to catch the gap that started this.
22. **High Court citations.** The neutral-citation work (A124, A125) is on and verified on **real High Court records**, not synthetic fixtures: `python -m evals.hc_identifiers --records <file>` is run on the launch collection and its yield (neutral citation found, case reference built, rejections by reason) is reported per court. The court-code table (`core/neutral_citation_courts.json`) was written from memory and is **unverified**; it is checked against the corpus. A High Court answer shows either a neutral citation exactly as printed, or a case reference with the owner-approved label (`CASE_REFERENCE_LABEL`), and **never a citation the model wrote**. The API schema and the web client must carry the two new `Passage` fields (they do not yet). The verifier's known residuals are decided, not left: A125 (a) a neutral citation of another case cited in a retrieved judgment's body counts as retrieved, (b) only the colon form is recognised, (c) the existing reporter shapes compare by substring ("AIR 1973 SC 146" accepted when "AIR 1973 SC 1461" was retrieved).
23. **High Court outcome statistics stay OFF** unless the High Court half of the 100-judgment `disposition` check shows a final-outcome field (`DECISIONS.md` top-5 question 2). The 577 disposition values are not cleaned. Supreme Court statistics keep their own gate (50-judgment check, pass rule agreed before checking).

**State Acts and regulators**

24. **`acts_noncentral_v1` is promoted into the launch collection** (A133; built and verified in staging, promotion is a separate decision and has not been taken). After promotion, on the launch collection: 0 differences between stored sparse vectors and a fresh BM25 encoding on a random 20,000-point sample; the central-Act repair (`data/sparse_fix.py`, 19,835 points) has been applied and shown likewise; and a keyword question made of a repaired provision's own words finds it, at a rate reported with its denominator (A133 measured 84% in the top 100 at 1.02M points, and said why it is not higher: wording repeats across states). The coverage page counts Acts by jurisdiction and instrument from the launch collection, not from a document.

**Evaluation**

25. **The 200-question set is extended for the full corpus and fully labelled.** It was written for the narrow corpus (A101). It gains High Court questions: **a floor of 2 per served court, plus 5 extra for each of the 8 largest courts by point count, roughly 90 new rows (owner, 4 Nov 2026). That floor is set by the advocate's budget, not by what would be ideal, and must not be read later as a judgement about how many questions give a good measure of a court.** The total therefore exceeds 200. **This grows the advocate's labelling job**, and its size is stated to the owner before the advocate is engaged: today 100 answerable rows are stubs with empty `expect_records`, and every new High Court row is another. **Tribunal questions** (rows with `expect_scope: needs_tribunal`, currently q107 to q112, written from the `{excluded:trib}` template so no tribunal name is typed) are **expected refusals and must pass as correct refusals** (A139). **When tribunals arrive, those rows flip to expected answers and must be re-labelled by the advocate, and new tribunal rows added; that work is not in this gate's budget and is costed separately then.** The set is frozen before any score is quoted. No row's expected answer is read from a pipeline run.
26. **The scorer's real-pipeline run (A103) is not accepted as evidence for this item.** It uses fake vendors; a pass there means the code path routes. Item 1 is scored against the real pipeline, real Jev and Gemini decisions, and the real corpus.

**Measurements that do not exist yet, and are required**

27. **Latency on the real server, real corpus, real vendors.** Every `CLAUDE.md` section 10 target is measured at the agreed load: first word, full answer, search stage (search plus re-rank, under 800 ms, **end to end including the query embedding**, owner, 4 Nov 2026), each Jev decision, Act lookup. **The report must give the breakdown**: query embed, Qdrant, fusion, re-rank, so a miss can be attributed. The embed was 1,140 ms p50 / 1,239 ms p95 on a laptop (A131). Qdrant itself was 4.7 ms p50 for one dense prefetch on 455,755 points; it has not been measured at the launch collection's size on the launch server. Targets are not changed to fit the numbers, and the 800 ms target is not redefined to exclude the slowest part (it is currently unreachable from a laptop, A131).
28. **Retrieval quality on the real corpus, per court.** recall@10 and recall@50 for dense, sparse and hybrid (`evals/known_item.py`, A100), reported per court with intervals, **plus** a set of natural-phrasing questions with real citation anchors written by the advocate. The existing numbers are on sentence-style and model-written paraphrase queries, which bracket production and neither is quotable (A128). The advocate set is the measurement that pins production.
29. **Single query model, confirmed.** The per-court query-model design is dropped (A128), so the launch collection is queried with **one model**. **The owner's answer is `voyage-4` (4 Nov 2026), unchanged by the run below.** **Partly measured already — see A136, written the same night as this gate and not reflected in its first draft.** The A128 lead (dense @10 +3.5, 95% CI +1.9 to +5.2; hybrid @10 +0.8, 0.0 to +1.5) was post hoc, and the confirmation on **fresh targets** has been run: 250 new targets from the 24-court corpus with the previously measured 250 and their source documents excluded, 1,161 queries. **Dense replicated but smaller (+1.6 @10, +0.3 to +2.9); hybrid did not (-0.1 @10, -0.9 to +0.7). The current decision is therefore `voyage-4`, unchanged (A136).** Do **not** re-run that comparison. **What remains required, and is the only thing left of G-M:** the same comparison over **the launch collection's real mixture of court models** (A136 used an 18,399-chunk sample, not the launch collection) and with **advocate-phrased queries**, because A138 records that the known-item harness sits at its hybrid ceiling (sentence-style hybrid 95.8%, moved by exactly 0 of 715 queries) and so cannot resolve a hybrid effect of a point or two either way. Read A136's hybrid null as "not detectable with that harness", not as "no effect". The chosen model is registered in config for the launch collection and a collection no one measured stays refused (A120).
30. **The net effect of every embedding-related choice is measured end to end, not inferred from a per-chunk cost.** A128's 5.4-to-0.56 estimate was wrong for exactly this reason (A128). Any later change to the query side (a model, a registry, fusion over several dense lists) needs an end-to-end number on the launch collection before it ships.
31. **Server size.** The sizing experiment (courts and Acts as served; no tribunal data is sized) has reported, the corpus fits the chosen instance with the load test of item 14 passing, and the monthly cost is in `COSTS.md`. The full corpus is about 45 to 55 GB of RAM before quantization (r7g.2xlarge, about $219 a month plus disk, four times the r7g.large floor); the experiment that settles it has not reported.

**Verifier on the full corpus**

32. **Verifier checks 1 to 4 run on High Court and State Act answers.** **The A137 strict rule (an unmarked sentence is removed) is built and tested first;** it is decided and not yet built. The invented-citation bait and the exists-but-not-retrieved bait (A101) include High Court and State Act cases, and a question that needs a tribunal decision must refuse as out of scope with the message read from `core/coverage.json`. The rule-f and digit-exemption changes (A117, A121) are deployed after the owner has reviewed the diff, and the measured fabricated-name acceptance (1 of 2,361, 0.04%, A122) is re-measured on a High Court title set.

**Open rows**

33. **No open owner row in `docs/DECISIONS.md` that blocks launch remains open.** This is read from `DECISIONS.md` on the day the gate is run; this section does not freeze the list, because other sessions add rows. Each row marked OPEN, NEEDS-OWNER, NOT DEPLOYED or "owner's call" is closed, or the owner writes a dated waiver beside it. As of 4 Nov 2026 the rows that would fail this item are listed in 7.4.
34. **Data and the facts it rests on.** The launch collection is built from the frozen snapshot v2026.08 (the question of v2026.08.1 is decided, 7.4). One point per `chunk_id` is verified by count. `core/coverage.json` is the only place a coverage category is written and `tests/test_coverage_source.py` passes.

### 7.4 Open rows that must close before launch (read from `DECISIONS.md`, 4 Nov 2026)

This is a snapshot, so a reader can see what the gate looked like on the day it was written. The authority is the file itself (item 33).

| Row | What is open | Owner |
|---|---|---|
| A124 | `CASE_REFERENCE_LABEL` wording (placeholder in config); court-code table verified; API and web carry the fields | Owner (wording); core and web lanes |
| A137 | **Decided (strict), not built.** An unmarked sentence is removed at pipeline step 9 (`core/verify.py`). The decision is closed; the build is not, and item 32 requires it built and tested before launch | Trust lane |
| A125 | Residuals (a), (b), (c) in item 22; strengthening the reporter-shape equality check alters an existing check | Owner and trust lane |
| A117, A121 | Verifier name-matching: NOT DEPLOYED, owner reviews the diff; `_NAME_SIDE` cap answered, not fixed | Owner and trust lane |
| A108 / A110 | `ACT_HEADER_STATUS_REPLACEMENT`, `ACT_STATUS_REPEALED`, `ACT_STATUS_IN_FORCE` wording (empty until the owner decides; these are statements about the law) | Owner |
| A133, A126, A132, A123, A129 | Promotion of staged collections into the launch collection (decisions separate from the builds) | Owner |
| Top-5 question 2 | `disposition` is final outcome or interlocutory (decides whether SC statistics ship, and rules High Court statistics out unless the HC half passes) | Hand check, advocate |
| "50-judgment SC pass rule" | How many must match; agree before checking | Owner and advocate |
| "Server size" | Sizing experiment | Core lane, owner |
| "The Code of Criminal Procedure, 1973" | State-file copy, official text, or leave out | Owner |
| "Snapshot v2026.08.1" | Upgrade (fills `source_url` on 83.3% of rows) or stay | Owner |
| "Upload auto-delete period", "Upload size and page limits" | Advocate's opinion; OCR time on real scans | Advocate |
| "Backup AI provider", "AI model per plan", "Order to switch on Jev uses" | Each provider's no-training terms; week-1 test | Owner |
| "GST in shown prices" (O9), "Plan prices" (O10), "Monthly answer limits per plan" | Accountant; deferred pricing | Owner, accountant |
| "Naming an advocate advisor publicly", counsel questions | BCI Rule 36 | Counsel |
| "Needs the owner" list | Placeholder user-facing sentences (`NEEDS-OWNER` in `web/src/lib/copy.ts`), what `cases.title` holds, retention periods (O13), Next.js upgrade, Qdrant hybrid never run on a live server, a real Firebase verifier injected into `create_app` | Owner, platform lane |

**Settled since the first draft of this gate (moved out of the open table on 4 Nov 2026):**

| Row | Settled as | Where |
|---|---|---|
| G-T, tribunals | **Launch ships without tribunals** (Branch 2, 7.0) | A139 |
| A128, which single query model | **`voyage-4`**, unchanged by the fresh-target run; the real-mixture, advocate-phrased comparison remains a measurement (item 29), not a question | A136, A128 |
| A138, known-item harness ceiling | Closed as a finding: read every hybrid null as "not detectable with this harness". Folded into items 21 and 29 | A138 |
| "What `acts_india` covers", "How the in-force rule treats state Acts" | Settled by A43/O7 and A181. The stale Open rows were moved to Settled in `DECISIONS.md` | A43, A181 |

### 7.5 Questions this gate put to the owner, and what is left

- **G-T. Answered:** launch ships without tribunals (A139, 7.0).
- **G-M. Answered:** `voyage-4` (owner, 4 Nov 2026; A136). Remaining: the real-mixture, advocate-phrased comparison in item 29.
- **G-L. Answered:** Kerala within 5 points of the median served court on hybrid @10 (item 21); question floor 2 per served court plus 5 for each of the 8 largest, roughly 90 new rows, set by the advocate's budget (item 25).
- **G-S. Answered:** the 800 ms search-stage target includes the query embedding (items 14, 27).
- **G-D. Open (owner):** the sentence says "anything after the data-as-of date"; the snapshot is labelled v2026.08 but the latest Supreme Court judgment held is dated 6 November 2025 (reported by the SC lane), so the date may be nine months after the content (A146).
- **G-W. Still open.** The `CASE_REFERENCE_LABEL` wording (item 22, section 8). It changes what a user is told about the law, so it stays the owner's; the placeholder stays.

**Re-read of items 1 to 34 against the 3 Nov scope (4 Nov, after A146).** Nothing is dropped. Not currently satisfiable: item 1 (it cannot be scored while 100 rows are unlabelled stubs) and item 14 (the 800 ms target, unreachable from a laptop on the embed alone, A131); both stay as written. Whose meaning moved: item 25, because the scope bucket for High Courts no longer refuses (the 8 trap rows now ask about district courts, `needs_lower_court`). Item 33 says "no open owner row that blocks launch remains open", and two new owner items (G-D above and the launch-scope-versus-served question, A146) are now among them.

**Superseded elsewhere in this file:** O6 and the "High Courts: Bombay, Telangana, Kerala, after launch" row in section 4.3 and section 3 row 7's "Open" status describe the MVP. Under the owner's 3 Nov decision all High Courts are in v1, and tribunals are excluded at launch (A139). Those rows should be edited by the owner or the lead; this revision changes only section 7.

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

Owner decisions O6, O9 and O13 above, and:

- **Where these additions came from.** The screens and patterns added on 2 Nov 2026 were taken
  from Harvey's own marketing videos and website (platform page, product playlist, academy
  library), watched and read in a working session. Everything Harvey says about itself —
  hours saved, lawyer counts, certifications, how its own system works — is a
  **Competitor claim**, recorded as such and never repeated as fact in our own copy. What we
  took is the *shape* of screens, not their wording, logo, typeface or layout.

- The exact coverage sentence shown to users (the owner's wording). It may name only what the measured coverage table shows (O7). Suggested shape, for approval: "LexBharat covers Supreme Court judgments and the Acts and regulations listed on our coverage page. It does not include High Courts, district courts, tribunals, or anything after the data-as-of date."
- Wording shown to users, including the two not-legal-advice sentences, the removal note,
  the consent text and the stats and sign-in text (placeholders marked `NEEDS-OWNER`).
- Retention periods and what `DELETE /me` keeps (counsel).
- What `cases.title` holds and whether it may ever be shown.
- The pass rule for the 50-judgment Supreme Court hand check (agree it with the advocate *before* checking).
- Upload size and page limits; upload auto-delete period (advocate's opinion).
- Final prices: deferred by the owner (O10). ₹199 and ₹499 are hypotheses; the website design doc's ₹799 is a labelled sample.

## 11. Change log

- **2 Nov 2026 (third):** added the screen patterns reviewed against Harvey (section 4.2:
  matters, split answer view, progress panel, follow-ups, improve helper, history, task
  cards, share links, memory); decisions O11 to O15; gate items 17 and 18; review tables
  and playbooks moved to after-launch; a longer not-building list.
- **2 Nov 2026 (later):** O7 decided (serve what the data holds, with a public coverage
  page); O8 decided (name is LexBharat); O10 added (pricing deferred). "KanoonBuddy" in
  this file and the original PDFs means the product now called LexBharat.
- **2 Nov 2026:** first revision. Widened v1 (O1); recorded owner decisions O1 to O9;
  corrected nine facts (section 3); added production, safety, legal and quality
  requirements (section 5); added the buy list (section 6); replaced the launch gate with
  a 16-point gate (section 7). Original PDFs unchanged.
