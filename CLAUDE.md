# CLAUDE.md

Rules for coding agents working in this repo. **Read this first, every session.**

Source of truth: [`docs/`](docs/). Where the PRD and the Tech Stack disagree, **the Tech
Stack wins**. Where this file and the Tech Stack disagree, the Tech Stack wins — and you
should fix this file.

---

## 1. What this is

**KanoonBuddy** (working name; entity **LexBharat**) is an AI legal research tool for
Indian lawyers and law students. A user asks a legal question in plain language and gets
a short plain answer where **every claim carries a citation that has been mechanically
verified against the dataset**.

The trust promise is the product. An answer with a fabricated citation is worse than no
answer. Everything below exists to protect that.

### v1 scope — do not widen it

| In v1 | Not in v1 |
|---|---|
| Supreme Court judgments | All High Courts (phase 2: Bombay, Telangana, Kerala) |
| `acts_india` (Central Acts) | Tribunals |
| Research chat with verified citations | Drafting / review / compare (P1) |
| Act + section lookup (free, public) | Hindi UI (P1) |
| Supreme Court outcome statistics (free, public) | Counter-arguments, moot court, study buddy (P2) |
| Upload-and-chat (built, behind a switch) | Data-refresh pipeline (post-MVP backlog, decision D2) |

Data is a frozen snapshot, **v2026.08**. There is no refresh pipeline in v1. Every result,
stats page and Act page shows its **data-as-of date**.

### Naming — everything is a placeholder

The product name, the collection name `kanoon_v1` and the folder name `kanoonbuddy/` are
**all placeholders**, pending a trademark search. Each lives in **one config value**
(`PRODUCT_NAME`, `CORPUS_COLLECTION`), so renaming is a config change, not a code change.

- **Never hard-code a product or collection name.** Read it from config.
- **Prefer neutral internal names in anything new** — `research_v1`, not a brand word.

---

## 2. The seven rules that keep it changeable

These are the architecture. Breaking one is a bug, even if tests pass.

1. **One adapter per outside service.** Every vendor (Voyage, Gemini, Jev, Firebase, S3,
   Razorpay, OCR) is called from exactly one file in `adapters/`. The rest of the code
   calls `embed(text)`, never the Voyage library directly.
2. **Settings live in config, not code.** Model names, API keys, limits, prices and
   thresholds sit in environment variables and one settings file. Changing the AI model is
   a config change.
3. **The frontend talks to the backend only through the API.** FastAPI publishes OpenAPI;
   the frontend's client is generated from it. No shared imports across `web/` and `api/`.
4. **Database changes go through migrations.** Alembic, numbered and reversible. No
   hand-edited schema.
5. **Everything runs in Docker.** One `docker compose up` starts the whole system on any
   laptop or server.
6. **Tests guard the trust promise.** The citation verifier and the usage meter have tests
   that must pass before any deploy. The 200-question test set runs on every release.
7. **Each pipeline step is a separate function with a fixed input and output.** Rewrite,
   decide, search, re-rank, gate, write, verify and format are each independently
   swappable.

---

## 3. Folder layout

```
web/          Next.js + TypeScript + Tailwind website (PWA)
api/          FastAPI app — routes only, no business logic
core/         pipeline steps: search, rerank, answer, verify
core/prompts/ prompt templates, as files
adapters/     one file per outside service
workers/      background jobs: OCR, indexing uploads (ARQ)
data/         scripts to build the launch collection from parquet + Qdrant
knowledge/    OKF knowledge notes (reviewed Markdown files)
evals/        200-question test set and scorer
tests/        unit and integration tests
migrations/   Alembic — numbered, reversible
infra/        docker-compose, deploy scripts
legal/        versioned consent notice, privacy policy, terms
docs/         PRD, Tech Stack, architecture, decisions
team/         people, lanes, the V1 plan, weekly plans
after-11-weeks/ the product at the end of the plan, and what comes next
.github/      PR template; CI and deploy workflows go in .github/workflows/
```

Business logic lives in `core/`, never in `api/` route handlers.

---

## 4. The research pipeline — 11 fixed steps

Every research answer goes through the same steps, in this order, every time. This is a
**fixed pipeline, not an agent**. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

1. **Remember** — last 6 turns in full + a rolling summary of older turns.
2. **Rewrite** — cheap model turns the message + context into one standalone query; pulls
   out any Act, section, case number or year.
3. **Decide (Jev)** — scope check, filters, safety check, which knowledge notes apply.
   Out-of-scope stops here with the coverage message.
4. **Cache** — exact match on (rewritten query + filters + model name) in Redis, 7 days.
   A hit costs nothing and does not count against the user's limit.
5. **Search** — dense (voyage-4) + sparse (BM25) in one Qdrant call, merged by Reciprocal
   Rank Fusion. Named sections and case numbers skip the merge and go to an exact payload
   filter. **Top 50.**
6. **Re-rank** — Voyage rerank-2.5-lite. **Top 10.**
7. **Gate (Jev)** — each passage rated answers it / partly / not relevant. Not-relevant is
   dropped. If none clears the threshold (0.6), the user gets "not found" and **nothing is
   written**. **At most 8 survive, labelled S1–S8.**
8. **Answer** — the model writes using only those passages plus any matching reviewed
   knowledge notes, and must put a source ID after every point taken from one.
9. **Verify** — the citation verifier. See §5.
10. **Show** — text streams word by word; the checked citations arrive as **one final
    event after verification**, with the data-as-of date, the CC BY credit and the
    not-legal-advice notice. A user must never see a citation appear and then vanish.
11. **Save** — message, source IDs, Jev decisions and confidence, model name, token counts.
    The usage meter counts one answer.

Passage counts are **50 → 10 → at most 8**. Do not change these without changing
`docs/DECISIONS.md`.

---

## 5. The citation verifier — the part that must never be weakened

Runs after the model finishes writing. A citation passes only if **all four** checks pass:

1. **Retrieved for this question.** The source ID was one of S1–S8 given to the model this
   turn. A real case the model recalled from training but that was not retrieved **fails**.
2. **Record exists.** That passage's `record_id` exists in `kanoon_v1`.
3. **Quotes match.** Any words in quotation marks appear in that record's text exactly,
   after normalising spaces and punctuation.
4. **Claim supported.** Jev rates whether the passage supports the sentence it is attached
   to: supports / partly / does not support.

Checks 1–3 are free, plain Python, and **always run — Jev up or down**.

A failed citation is **removed** from the answer, the answer notes that one authority could
not be verified, and a row is written to `invented_citation_log` with the reason (not
retrieved, record missing, quote not found, claim not supported).

### What the tick means — and does not

| The tick means | The tick does NOT mean |
|---|---|
| The cited case or section exists as a record, matched by its record ID | That it is good law — it may be overruled, distinguished or reversed |
| Quoted words appear in that record's text | That the quote is the holding, or that the AI's summary is right |
| The link goes to the record's `pdf_url` / `source_url` | That the link works today or the text is current law (snapshot v2026.08) |
| A stored citation string is shown exactly as recorded | That the citation string is correct or complete |

Wording shown to users: **"Record found in dataset"**, with the data-as-of date. Ticks are
**per citation**, never one badge for the whole answer.

**Never** retype or reformat a Supreme Court citation string with the AI. Show it exactly
as stored, labelled "as recorded in the dataset".

---

## 6. Hard rules — do not violate these

### Privacy and data
- **Upload text never reaches Jev, Langfuse or Sentry.** In upload chats, the claim-support
  check and any decision touching upload text uses Gemini (paid tier) instead.
- **Every query touching uploads goes through one shared data-access function** that always
  adds the `user_id` filter. No feature writes its own Qdrant or upload query. A missing
  filter leaks one lawyer's client files to another.
- **Only models on no-training terms.** The model list in config accepts only providers
  marked "no training". Never a free tier that may train on user data.
- Langfuse logs are **masked** (upload text, emails, phone numbers → placeholders). Sentry
  reports are **scrubbed** (request bodies, tokens, emails, document text removed).
- Delete means **hard delete**: file from S3, extracted text from PostgreSQL, all vectors
  from Qdrant by `document_id`, in one job, logged, with a nightly leftover check.

### Data you must not trust
- **Never display judges or party names.** `judges` is 32.7% filled and sampled values were
  extraction garbage; `petitioner`/`respondent` are 99.9% filled but often counsel names or
  sentence fragments (Measured).
- **Show the in-force flag only where `act_status` is filled** — it covers 1,568 of 22,264
  acts. Label every other Act result "in-force status not checked".
- **High Courts have no citation strings** (0.0% filled). The verifier falls back to record
  existence and quoted text, and High Court answers show no citation string.
- **Never compete on document counts.** `case_id` is not one per case — Rajasthan has
  1,056,767 `case_id` against 308,342 distinct `case_number`.
- Full field-quality table: [`docs/DATASET.md`](docs/DATASET.md).

### Legal and regulatory
- **Not legal advice.** Every answer, stats page and Act page carries the notice. When
  Jev's safety check flags a personal-advice question, the answer opens by saying it cannot
  advise on the user's own situation.
- **BCI Rule 36.** No listing, ranking, matching or recommending advocates. No "find a
  lawyer". No named advocate testimonials. Share cards and stats pages never name an
  advocate.
- **No judge or party names displayed** — the PRD's audit found those fields unreliable.
- **Outcome statistics are descriptive only.** Counts, never predictions or win chances.
- Every page and share card carries the data-as-of date and the CC BY credit:
  `Data: Open India Law by Vaquill AI, CC BY 4.0`.

### Build and deploy
- **Never touch the production server directly.** Push to GitHub; GitHub Actions deploys.
- **Never commit secrets.** API keys live in AWS Secrets Manager; locally in `.env`, which
  is gitignored. `.env.example` lists names only.
- **Never print a secret.** Do not `cat`, `echo`, `head` or otherwise display `.env`,
  `settings.json` or any credentials file. To check a key exists, use
  `grep -c KEY_NAME file` or test that the variable is set, without showing its value.
  Redact any secret before it goes into output, a doc or a commit message. (A live API key
  was once printed this way and had to be rotated.)
- The server is **ARM (Graviton, r7g)** — every Docker image needs an ARM build.

---

## 7. Do not use

- **Full LangChain.** Small pieces (e.g. text splitters) are fine. The framework is not.
- **Any orchestration that lets an answer skip the verifier.** Agent orchestration inside
  the product is now **allowed** (owner decision, 1 Nov 2026), but only where the final
  answer always passes through the citation verifier (§5) and the gate (step 7) afterwards,
  with the verifier code outside the agents' control. The 11-step research pipeline in §4
  stays a fixed pipeline; orchestration is for features with real branching
  (counter-arguments, moot court, drafting, review).
- **CrewAI / LangGraph for the research pipeline itself.** Not needed; the fixed pipeline is
  cheaper, faster and easier to debug. Use them only for the branching features above, and
  record the choice in `docs/DECISIONS.md` first.

---

## 8. Explain the code as you write it

This product is built solo with AI agents by someone who has to **own and maintain** what
gets written. Code the owner cannot read is a liability, not an asset — the whole repo is
one bus-factor away from being unmaintainable.

So, on every non-trivial change:

- **Say what it does in plain words first**, then show the code. Not the other way round.
- **Name the file and line** — `core/verify.py:42` — so it can be opened and checked.
- **No unexplained jargon.** If a term is unavoidable, define it in one clause. The Tech
  Stack has a plain-words glossary for exactly this reason; add to
  [`docs/GLOSSARY.md`](docs/GLOSSARY.md) rather than assuming the word is known.
- **Draw anything with a flow.** The pipeline, a request path, a data model, a failure
  path — a diagram beats three paragraphs. Render it inline rather than describing it.
- **Say which of the 11 pipeline steps** a change touches, every time.
- **Show the evidence.** "Tests pass" means the output. "It works" means the thing running.
  Never claim a check passed that was not run — say "not verified" instead.
- **Flag the trade-off you made** and what you ruled out, in one line. A choice the owner
  cannot see is a choice they cannot overrule.

Writing more code faster is not the goal. The goal is a product its owner can defend to an
advocate, a regulator and the next engineer.

### Who decides (agent-built mode, from 1 Nov 2026)

The owner has asked for the build to be done **completely by agents**. So agents decide
technical design themselves, including `core/`, the adapters and the data model. What
changes is *how visible* the decision is:

1. Make the call. Pick the simplest option that follows the seven rules in §2.
2. **Record every non-obvious choice in `docs/DECISIONS.md` in the same commit**: the choice,
   the one alternative ruled out, and why, in one or two lines.
3. Then build, explaining as in §8 above.
4. Push back on a bad instruction, in the commit message or the final report.

**Still the owner's call. Stop, do the preparatory work, and write the question into the
final report** — do not guess — for:

- anything that changes what a user is told about the law (UX copy about advice, privilege,
  the not-legal-advice line, BCI Rule 36 wording);
- weakening or skipping any verifier check (§5), or changing the 50 → 10 → 8 passage counts;
- pricing, plans, the product name, retention periods;
- spending money or using a real API key or production system;
- anything in `docs/DECISIONS.md` marked open that needs a lawyer, an advocate or Vaquill.

> If the **Vibe Wise** plugin is loaded in this session, its learning-first mode takes
> precedence over this section.

## 9. How to work here

1. Build **one small feature at a time**, each with tests. Run the tests before saying it
   is done.
2. Use a second agent or a fresh session to review each change against §2.
3. When you touch the pipeline, state which of the 11 steps you changed.
4. When you make a decision the docs left open, record it in
   [`docs/DECISIONS.md`](docs/DECISIONS.md) in the same change.
5. Facts in docs carry evidence labels — keep them: **Measured**, **Checked**,
   **Dataset card**, **Competitor claim**, **Estimate**, **Needs verification**. Do not
   promote an Estimate to a fact without measuring it.
6. **Verify before claiming.** Do not state a fact about the dataset, a source, a refresh
   cadence or a missing field until you have checked it with a command or a file read.
   Label anything unchecked **"unverified"**. Before writing docs from a long source such as
   the PRD, read the **whole** document, or summarise it section by section first. (The
   first docs here were drafted after reading 3 of 59 PRD pages and had to be corrected.)

7. **Two ways to work, pick one per session.**
   - **Single task (default for people):** one GitHub issue = one branch = one pull request
     = one Claude session. Start with `/start-task <issue>`, end with `/finish-task <issue>`.
     If a task outgrows one session, finish a clean slice and propose a follow-up issue.
   - **Agent build (owner-run, see §12):** one branch (`shan/agent-build`), several agents
     working in parallel on separate folders, one pull request to `main`. The owner reviews
     and merges. Agents never push to `main`.

### Environment

The owner is on **macOS**. Agent builds may run on Linux in the cloud: anything you write
must still work on macOS and on the ARM server.

- Use macOS/BSD-compatible commands. There is **no GNU `timeout`** — use `gtimeout`, or a
  background-and-kill pattern.
- Give long-running service starts, such as Qdrant, **at least 60 s** before calling them
  failed.
- **Never revert a config placeholder** (for example an `API_URL`) after local testing
  without saying which URL the app will use afterwards.
- When the owner must run something themselves, give the exact copy-paste command and say
  **where** to run it: Terminal, or the Claude desktop app.

### Skills and commands

This repo carries its own skills in `.claude/skills/` — they load automatically when they
fit the work (the verifier, pipeline steps, vendor adapters, corpus fields, uploads,
knowledge notes). Commands you can type: `/start-task`, `/finish-task`, `/trust-check`,
`/decision`, `/where`, `/ship`.

Installed **marketplace** skills worth reaching for on this project:

- **`rag-architect`** — build step 2. Retrieval evaluation (precision@k, recall@k, NDCG).
  The plan currently has **no retrieval-quality metric at all**; this supplies one.
- **`ai-security`** — any time. Prompt injection. User questions **and uploaded documents**
  reach models, so a hostile PDF is an attack surface nobody has reviewed yet.
- **`impeccable`** — build step 4. `docs/KanoonBuddy-Website-Design-Doc-v2.md` is a ready brief.
- **`ux-researcher-designer`** — build steps 9–10. The 20 validation interviews.

Full table, including the ones that **look** relevant but would produce wrong work (the
GDPR skills — India uses DPDP; Stripe — this uses Razorpay; Kubernetes — this is one box
with Docker Compose): [`.claude/README.md`](.claude/README.md).

### Commands

Nothing is scaffolded yet — fill these in as you build, and keep them true.

```bash
docker compose -f infra/docker-compose.yml up    # whole system
# api:    (to be added)
# web:    (to be added)
# tests:  (to be added)
# evals:  (to be added — 200-question test set)
```

---

## 10. Performance targets

| Measure | Target |
|---|---|
| First word of a research answer | under 3 s |
| Full research answer | under 20 s |
| Search stage (search + re-rank) | under 800 ms |
| Each Jev decision | under 800 ms, or Gemini fallback takes over |
| Act / section lookup | under 500 ms |
| Upload ready: text PDF under 50 pages | under 60 s |
| Upload ready: scanned PDF under 50 pages | under 5 min |
| API availability | 99.5% a month |

Measure in Langfuse from week 1. **Watch first:** Qdrant memory and OCR time — the two
things expected to break first on a 16 GB server.

---

## 11. Where to look

| Question | File |
|---|---|
| **What must be answered before writing code?** | [`docs/DECISIONS.md`](docs/DECISIONS.md) — top 5 |
| How does an answer get produced? | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| What was decided, and what is still open? | [`docs/DECISIONS.md`](docs/DECISIONS.md) |
| Who is this for, what ships, what does it cost? | [`docs/PRODUCT.md`](docs/PRODUCT.md) |
| **Can I trust this field?** | [`docs/DATASET.md`](docs/DATASET.md) |
| What tables and collections exist? | [`docs/DATA-MODEL.md`](docs/DATA-MODEL.md) |
| What routes exist, and what shape? | [`docs/API.md`](docs/API.md) |
| How does verification work in detail? | [`docs/CITATION-VERIFIER.md`](docs/CITATION-VERIFIER.md) |
| **What exactly does the user see when something fails?** | [`docs/UX-COPY.md`](docs/UX-COPY.md) |
| What do I build next? | [`docs/BUILD-ORDER.md`](docs/BUILD-ORDER.md) |
| When does this ship? | [`docs/ROADMAP.md`](docs/ROADMAP.md) |
| What are we measuring, and what gates launch? | [`docs/METRICS.md`](docs/METRICS.md) |
| What could go wrong? | [`docs/RISKS.md`](docs/RISKS.md) |
| What are the legal constraints? | [`docs/SECURITY-AND-COMPLIANCE.md`](docs/SECURITY-AND-COMPLIANCE.md) |
| How long do we keep data? | [`docs/RETENTION.md`](docs/RETENTION.md) |
| Something leaked — what now? | [`docs/BREACH-PLAYBOOK.md`](docs/BREACH-PLAYBOOK.md) |
| The server is down / how do I deploy? | [`docs/RUNBOOK.md`](docs/RUNBOOK.md) |
| What config does this need? | [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md) |
| What must pass before I ship? | [`docs/TESTING.md`](docs/TESTING.md) |
| What does this word mean? | [`docs/GLOSSARY.md`](docs/GLOSSARY.md) |
| How do knowledge notes work? | [`knowledge/index.md`](knowledge/index.md) |
| What legal documents are missing? | [`legal/README.md`](legal/README.md) |
| What skills and commands exist here? | [`.claude/README.md`](.claude/README.md) |
| Which skills did we plan, use or reject? | [`skills-used/README.md`](skills-used/README.md) |
| Who works on what, and how does work reach `main`? | [`team/README.md`](team/README.md) |
| What does the product look like after 11 weeks, and what's next? | [`after-11-weeks/`](after-11-weeks/README.md) |

## 12. Agent build lanes (branch `shan/agent-build`)

Used when the owner runs an agent build (§9.7). Agents work in parallel in **one checkout**,
so each owns a folder and never edits another's. Shared files (`pyproject.toml`, `CLAUDE.md`,
`docs/DECISIONS.md`) are edited only by the lead agent.

| Lane | Owns | Builds |
|---|---|---|
| Core + Data | `core/`, `adapters/`, `data/`, `evals/`, `tests/core/` | adapters with fakes, verifier checks 1–3 + tests, one function per pipeline step, eval scaffold |
| Platform | `api/`, `migrations/`, `docker-compose*.yml`, `.github/`, `tests/api/` | FastAPI routes, Alembic migrations per `docs/DATA-MODEL.md`, ARM-aware Docker, CI |
| Web | `web/` | chat, citation ticks, failure screens, Act/judgment pages on the shared design tokens |
| Reviewer | read-only | runs all tests and checks the work against §2 and §6; reports, does not fix |

Rules for every lane: use fakes for Voyage, Gemini, Jev, Firebase, S3, Razorpay (no real keys);
state "not verified" for anything that was not actually run; commit small and often.
