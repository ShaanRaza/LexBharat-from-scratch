# Decisions

Two lists: **settled** (do not relitigate without a new entry here) and **open** (each with
what will settle it). From the Tech Stack's "Open decisions" and change log.

When you settle an open decision while building, move the row up, add the date and the
evidence, and note it in the commit.

---

## Top 5 questions to answer before writing code

Ranked by how much the answer would change the plan. **None is answered by the dataset;
each needs a person, a hand check or a lawyer.**

| # | Question | What answers it | What it would change |
|---|---|---|---|
| 1 | **Will advocates and students pay, and how much?** | The 20 validation interviews | If the answer is "not at these prices", pricing and the whole go-to-market change |
| 2 | **Does `disposition` describe the final outcome or an interlocutory order?** | The 100-judgment hand check (50 SC, 50 HC) in weeks 1–2 | The SC half can clear SC statistics on its own; if the HC half shows a mix, **High Court statistics cannot ship** |
| 3 | **How do the first 100 users find us?** | A yes or no from at least two law schools on a pilot, and a test of whether free indexed pages get search traffic | **Without distribution, the product does not matter** |
| 4 | Who builds it, and what is the budget? | **Decided: one solo builder with AI coding agents.** Time build steps 1 and 2, then re-plan | The weeks 3–10 schedule fits only the 3-engineer plan |
| 5 | **What do counsel and Vaquill say?** | A lawyer on privilege, the DPDP role and the advice line; Vaquill on the three questions in [DATASET.md](DATASET.md) | Either conversation can force a scope change |

### Other open questions

- Voyage per-query cost and monthly budget on real questions (build step 2).
- Is the chunk gap ~55,000 or ~1.15M? **Partly answered for the Supreme Court** (Measured, 13 Oct 2026): the parquet's 1,113,313 rows are 371,247 English chunks plus translations in 15 languages; Qdrant holds the English ones (371,159, a gap of 88). But Qdrant has 34,954 cases against 35,596 English cases in the parquet (642 missing). Full reconciliation: issue #16.
- Hindi-first or English-first for the interface and answers?
- Trademark search on the final name **and** the five alternatives, before any branding spend.
- Monthly LLM budget per paying user — measure on the 200-question test set.
- Whether to extract tribunal data after launch (OCR effort, not licensing).
- Who cleans the High Courts' 577 disposition values, and to what standard? Phase 2.
- Will TypeSafe grant Jev early access and confirm no-training terms in writing?
- Server size — does SC + `acts_india` fit on r7g.large (16 GB)? The counts are now Measured (below); the load test isn't done.
- Firebase or Supabase — stay until a trigger is hit; decide at each trigger.

---

## Settled

| # | Decision | Choice | Why |
|---|---|---|---|
| D1 | Supreme Court outcome statistics | Ship in v1, gated on the 50-judgment hand check | Disposition values are concentrated in ~10 readable outcomes (Measured) |
| D2 | Data refresh pipeline | **Not in MVP.** Ship on snapshot v2026.08 with a data-as-of date; refresh goes to the post-MVP backlog | Keeps v1 small; overrides the request to add it as a build step |
| D3 | Hindi | P1 — within 3 months of launch, P0 if the 20 interviews show strong demand | Needs a Devanagari-aware BM25 tokenizer; not a v1 blocker |
| D4 | CC BY credit text | `Data: Open India Law by Vaquill AI, CC BY 4.0` on every result, page and share card | Licence condition |
| D5 | Launch gate condition 6 | "Data-as-of date shown prominently" replaces "first data refresh complete" | Follows from D2 |
| D6 | Not-legal-advice notice | On every answer, stats page and Act page; stronger when Jev flags personal advice | BCI Rule 36 + the information/advice line |
| — | Keyword search | BM25 sparse vectors inside Qdrant | Settles the PRD's PostgreSQL-FTS vs Qdrant choice; also covers "Voyage is down" |
| — | Agent framework inside the product | **Research pipeline: none, fixed 11 steps. Orchestration allowed for branching features** (owner decision, 1 Nov 2026) | Verifier and gate must always run after any orchestrator; see CLAUDE.md §7 |
| — | How the v1 build is run | **Agent build on one branch `shan/agent-team`**, 3 build lanes + reviewer, one PR to `main` | Owner asked for agent-built work; folders partitioned to avoid conflicts (CLAUDE.md §12) |
| — | Send upload text to Jev | **Never.** Upload chats use Gemini (paid tier) for those checks | Privilege and DPDP risk; Jev runs in the US |
| — | Answer cache lifetime | 7 days | Tune from real use |
| — | Re-embed SC chunks with a header | Keep Vaquill's vectors as they are | Compare on the test questions in build step 1 |
| — | Hosting the website | Same EC2 server | Move only if the server gets busy |
| — | Supabase / Cognito migration | Stay on Firebase | Move only on the triggers in Login and payments |
| — | Phase 2 court order | Bombay, Telangana, Kerala | Archive depth: 45.0%, 45.4%, 39.9% of cases predate 2015 (Measured). Delhi next, for practical demand |
| — | OCR for scans | Tesseract only | Textract later if 20 real court scans show it is needed |
| — | Re-ranker backup | Open-source bge-reranker on the server | If it fits in 16 GB alongside everything else |
| — | Model routing (easy/hard) | **Off at launch** | Turns on only once a stronger model is chosen |
| — | Jev gate threshold | Start at 0.6 (Estimate) | Set from the 200-question test set |
| — | Voyage free allowance | Assume 200M tokens once, not monthly | Confirm with Voyage |
| — | Upload embedding model | voyage-4 first, free local model (bge-m3) as fallback | Depends on Voyage's upload terms and the legal opinion |
| — | What `DELETE /me` keeps | Payment and invoice records only | Needs counsel to confirm the retention period |
| — | **Court field in the Qdrant payload** (13 Oct 2026) | `court_type = "supreme_court"` (also `court = "Supreme Court of India"`; both give the same count). Both fields are indexed | **Measured** with `data/inspect_collections.py`. Not `court = supreme_court`, as earlier notes assumed |
| — | **Supreme Court point count** (13 Oct 2026) | **371,159 points, 34,954 cases, all in `legal_corpus_v2`.** `legal_corpus_v1` has **none** (it's High Courts only). English chunks only; every point has its chunk text in the payload | **Measured.** The search collection is built from `legal_corpus_v2` alone |

---

## Open — blocking or near-blocking

| Decision | Options | Working choice | What settles it |
|---|---|---|---|
| **Final product name** | KanoonBuddy (working) or Praman (PRD's pick) | Undecided | Trademark search with IP India |
| **Server size** | r7g.large (16 GB) or r7g.xlarge (32 GB) | r7g.large | Counts are Measured: 371,159 SC points + up to 1,098,577 `acts_india` points (fewer if v1 serves Central Acts only). Load-test search with quantization |
| **What `acts_india` covers in v1** | Central Acts only (74,509 points) / + state Acts (469,714) / + regulations (554,354) | Undecided. CLAUDE.md and the PRD say "Central Acts"; `docs/UX-COPY.md`'s coverage message says "central and state Acts and regulations" | Shaan decides **before the search collection is built (issue #15, Day 3)**. Measured 13 Oct 2026: the collection holds all three (`jurisdiction` facet) |
| **50-judgment SC pass rule** | How many must match for stats to go live | Undecided | Agree with the advocate **before** checking |
| **Upload auto-delete period** | 7, 30 or 90 days | Undecided | Advocate's legal opinion |
| **Upload size and page limits** | e.g. 25 MB and 200 pages | Undecided | OCR time on real scans; what interviewees upload |
| **Backup AI provider** | OpenRouter, Groq, or a second big vendor | Undecided | Each provider's no-training terms |
| **GST in shown prices** | Included or added | Undecided | Accountant |
| **Data-refresh method** | Run scrapers, or license a daily sync from Vaquill | Undecided (post-MVP, D2) | Vaquill's reply on price and deltas |
| **Snapshot v2026.08.1** | Upgrade (fills `source_url` on 83.3% of rows) or stay | Undecided | Build step 1, evaluated against download time |
| **How the in-force rule treats state Acts and regulations** | Show status only for Central Acts / show it for all / label the rest "in-force status not checked" | Undecided. CLAUDE.md §6 says "show it only where `act_status` is filled (1,568 of 22,264 Acts)", but **`act_status` is filled for all 22,264** (Measured, 13 Oct 2026). Only the 1,568 Central Acts carry repealed or spent; every state Act says `in_force`, which looks like a default. Applied literally, the rule would label every state Act in force | Shaan decides, with the `acts_india` scope decision above. Fix CLAUDE.md §6 and `docs/DATASET.md` in the same change |
| **The Code of Criminal Procedure, 1973** | Use a state-file copy (state amendments mixed in) / source the official text separately / leave CrPC out | Undecided. It isn't in the Central Acts file; copies exist only in state files (Maharashtra, Punjab, Uttar Pradesh, Chhattisgarh) (Measured, 13 Oct 2026) | Decide before the CrPC → BNSS law map (Week 7) |
| **Duplicate points in `legal_corpus_v2`** | Remove duplicates by `chunk_id` when building the search collection | Some chunks are stored twice under different point IDs (Measured: 1 of 20 sampled judgments). Not yet counted across the collection | Count them in issue #16; remove them in issue #15 |
| **AI model per plan** | Gemini Flash-Lite family, Claude, GPT, Kimi K3 | Free: Gemini 2.5 Flash-Lite; Student/Pro: Gemini 3.1 Flash-Lite | Week-1 test on 50 real questions: correctness, cost, speed |
| **Order to switch on Jev uses** | All at launch, or one at a time | Offline cleaning first, then gate and claim support, then the rest | Test results and early-access availability |
| **Which notes beyond the first set** | Grow by topic, or only where answers go wrong | Only where answers go wrong | Wrong-answer reports and test-set failures |
| **Who reviews knowledge notes** | Advocate advisor, or a paid one-off reviewer | Advocate advisor | Quote for reviewing the law maps |
| **Interface language** | Hindi-first or English-first | Open (from the PRD) | The 20 interviews |
| **Plan prices** | Free ₹0 / Student ₹199 / Pro ₹499 / Chambers ₹299 per user | Proposed, **untested** — no lawyer has been asked | The 20 interviews; see the evidence table in [PRODUCT.md](PRODUCT.md) |
| **Monthly answer limits per plan** | Undecided | Undecided | Measured cost per answer from the week-1 test, set so a heavy user still leaves a margin |
| **Naming an advocate advisor publicly** | Counts as publicity under BCI Rule 36? | Unknown | Needs counsel |

---

## Agent build decisions (branch `shan/agent-team`, 1 Nov 2026)

Made by the agent team under CLAUDE.md §8 "Who decides". Each row: the choice, the one
alternative ruled out, and why. **Rows marked OWNER need your confirmation** because they
touch the trust promise or what users see.

| # | Lane | Decision | Ruled out | Why |
|---|---|---|---|---|
| A1 | core | **OWNER.** Answer seal is an HMAC over the answer content, keyed by `SEAL_KEY` (stable across processes, never hard-coded); `seal_answer` exists only in `core/verify.py`, `show()` rejects unsealed answers, a tree-scan test enforces it | A bare sentinel object | A sentinel is forgeable and survives `dataclasses.replace` (reviewer MAJOR) |
| A2 | core | Production start fails if `SEAL_KEY` is empty; every Fake raises if `ENVIRONMENT=production` | Fakes allowed anywhere | Fake answers must never reach users |
| A3 | core | Jev off, slow or down falls back to Gemini with the same fixed choices; `DecisionUnavailable` only if both fail; upload text never goes to Jev (`decide(..., uploads=True)`) | Sending upload text to Jev | Privilege and DPDP risk |
| A4 | core | Usage check runs **first**, before any AI call; over-limit users get no cache hits either | Checking after the cache | A cache lookup needs the rewrite, which is an AI call |
| A5 | core | If every decider is down, step 3 continues as in scope with `safety=personal_advice` | Blocking the question | Only strengthens the disclaimer |
| A6 | core | Voyage down: keyword-only search flagged `keyword_only`; re-rank keeps search order | Failing the request | Matches the Architecture failure state |
| A7 | core | Older conversation turns fold into the summary by truncation, not an LLM call | An LLM summary per turn | Cost; revisit with real use |
| A8 | core | Contracts are stdlib dataclasses; platform maps them to its own schemas | Pydantic in `core/` | Keeps `core/` independent of the API |
| A9 | core | Year-range filters applied in Python after search; exact section and case-number lookups use payload filters | Qdrant range filters | Simplest first version; measure later |
| A10 | trust | **OWNER.** Jev and Gemini both down on check 4 gives `partly`, never `verified`, citation kept | Removing every citation during an outage | An outage must not wipe all citations; checks 1-3 still run and still remove |
| A11 | trust | A sentence whose only citations all fail is dropped, not left uncited | Leaving an uncited claim | Every claim carries a verified citation |
| A12 | trust | Unbalanced or unpairable quote marks fail closed (citation removed as `quote_not_found`); every quote anywhere in the answer must appear in a retrieved passage | Guessing what was quoted | A quote that cannot be matched cannot be trusted |
| A13 | trust | Gate with the decision adapter unavailable uses the re-rank score against the same 0.6 threshold | Pass-through or refuse-all | Pass-through weakens the gate |
| A14 | core | **OWNER.** An answer with **zero surviving citations is refused** (`not_found`), whether all failed or none were written | Showing uncited prose with a disclaimer | CLAUDE.md §4 step 8: every point needs a source ID |
| A15 | core | Prompt `core/prompts/answer.txt` forbids naming any case, Act or section outside S1-S8, guarded by a test | Relying on regex alone | Regex cannot catch a recalled case with no "v" or "In re" |
| A16 | platform | `APP_ENV` defaults to `production`; fake pipeline needs `APP_ENV` in development/test **and** `ENVIRONMENT != production` | Default development | A forgotten variable must not enable fakes |
| A17 | platform | Invalid token gives 401; adapter error or no verifier wired gives 503; both deny | Allowing on error | Fail closed |
| A18 | platform | Wire contract: one `citations` event (with `removed_count`, `data_as_of`, `credit`, `notice`); `done` carries `refused`, `reason` (`out_of_scope` or `not_found`), `message_key`; usage limit is an `error` event with `quota_exceeded` | Reason inferred by the client | Web cannot tell out-of-scope from not-found otherwise |
| A19 | platform | Sync SQLAlchemy in a thread pool | Async engine | Async needs the extra greenlet dependency |
| A20 | platform | Usage meter allows when `PLAN_LIMIT_*` is unset | Blocking everyone | Limits are undecided (your call) |
| A21 | platform | `alembic.ini` lives in `migrations/` (`alembic -c migrations/alembic.ini`) | Repo root | Keeps the lane's files together |
| A22 | platform | API-only config (`APP_ENV`, `WEB_ORIGIN`, `FAKE_PIPELINE`) lives in `api/config.py` | Adding to `core/settings.py` | That file is core's; fold in later if wanted |
| A23 | web | Fake mode must be exactly `"true"`, throws in production, shows a DEMO banner | Default on | Canned ticks in production would be a trust breach |
| A24 | web | A stream that ends without `done` is a service error and the partial text is cleared | Leaving partial text | No answer without citations |
| A25 | web | **OWNER.** Case titles are shown nowhere (they are party names, CLAUDE.md §6); a judgment is named by its stored citation string, else case number, else "Supreme Court judgment, year". API also drops judgment titles | Showing the title | Reversible in `citationName()` and `judgmentHeading()` |
| A26 | web | Client is hand-written from `api/schemas.py` until `/openapi.json` generation exists | Generated client | No generator wired yet; CLAUDE.md §2 rule 3 says generate later |
| A27 | lead | Added `pydantic>=2`, `litellm`, ruff `S`/`BLE` security rules and `pythonpath` to `pyproject.toml`; `SEAL_KEY`, `DATA_CREDIT`, `ENVIRONMENT` names to `.env.example` | n/a | Boilerplate |

### Needs the owner (collected from the team)

- A1, A10, A14, A25 above.
- Wording shown to users: usage-limit, service-error and personal-advice-opener sentences, the removal note, the consent text and notice version are **placeholders** (marked `NEEDS-OWNER` in `web/src/lib/copy.ts`). `docs/UX-COPY.md` describes but does not quote them.
- What `cases.title` holds, and whether it may ever be shown.
- Upgrade Next.js 16.4.0? `npm run build` prints a known-vulnerability notice and alternates between passing and failing; nobody ran the upgrade.
- Real Jev client is a stub (API undocumented) and real Qdrant store is dense-only (no BM25 / RRF): both need your keys and docs.
- Production needs a real Firebase verifier injected into `create_app`; until then every protected route returns 503.

---

## Known documentation conflict

| Doc | Launch courts |
|---|---|
| PRD p.2 | Supreme Court + `acts_india` only; Bombay, Telangana, Kerala in phase 2 |
| Website Design Doc v2 (as received) | Supreme Court + Delhi, Bombay, Madras High Courts |

**Resolved 9 Oct 2026: the PRD is correct.** The website design doc was corrected in this
repo. Delhi and Madras appear nowhere in the PRD's phase-2 list — if the website copy came
from a third source, that source is also wrong.

### Second conflict: Pro price

| Doc | Pro price |
|---|---|
| PRD, p.37 | **₹499 a month** (₹4,990 a year) |
| Website Design Doc v2, pre-launch checklist | ₹799, explicitly labelled a **sample** pending confirmation |

The design doc flags its own figure as a sample, so this is a placeholder that was never
updated rather than a contradiction of record — but the PRD already proposes a real number.
**Not changed in this repo pending a decision**, because ₹499 is itself untested.
