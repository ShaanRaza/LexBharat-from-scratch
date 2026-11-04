# LexBharat — KanoonBuddy

AI legal research for Indian lawyers and law students. Ask a legal question in plain
language; get a short plain answer where **every claim carries a citation that has been
mechanically verified against the dataset**.

> **Working name.** "KanoonBuddy" is a working name pending a trademark search; the PRD
> recommends "Praman". `PRODUCT_NAME` is a single config value, so the final brand is a
> config change, not a code change. Never hard-code it.

<!-- coverage:begin -->**Coverage (measured 2026-11-04):** LexBharat covers Supreme Court and High Court judgments and the Central Acts listed on our coverage page. It does not include district courts, tribunals, or anything after the data-as-of date. (NEEDS-OWNER: wording not approved) Generated from `core/coverage.json`; do not edit by hand.<!-- coverage:end -->
Data is a frozen snapshot, **v2026.08** — every result shows its data-as-of date.

KanoonBuddy gives legal information, **not legal advice**.

---

## Start here

| If you are | Read |
|---|---|
| A coding agent | **[CLAUDE.md](CLAUDE.md)** — first, every session |
| A new teammate | **[team/README.md](team/README.md)** — your lane, first-time setup, how work reaches `main` |
| Looking for today's task | **[This week's issues](https://github.com/ShaanRaza/LexBharat/milestones)** — status lives there, not in the files |
| Picking up the build | [docs/BUILD-ORDER.md](docs/BUILD-ORDER.md) and the [V1 plan](team/V1-PLAN.md) |
| Wondering where this ends up | [after-11-weeks/](after-11-weeks/README.md): the product on 4 Jan 2027, and what comes next |
| Trying to understand the system | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Wondering why something is the way it is | [docs/DECISIONS.md](docs/DECISIONS.md) |

## Repo layout

```
web/          Next.js + TypeScript + Tailwind website (PWA)
api/          FastAPI app — routes only
core/         pipeline steps: search, rerank, answer, verify (+ prompts/)
adapters/     one file per outside service
workers/      background jobs: OCR, indexing uploads
data/         scripts to build the launch collection from parquet + Qdrant
knowledge/    OKF knowledge notes (reviewed Markdown)
evals/        200-question test set and scorer
tests/        unit and integration tests
migrations/   Alembic — numbered, reversible
infra/        docker-compose, deploy scripts
legal/        versioned consent notice, privacy policy, terms
docs/         specs and reference
skills-used/  record of which skills were planned, used or rejected
team/         who works on what, branch rules, the V1 plan, weekly plans
after-11-weeks/ the product at the end of the plan, and what comes next
.claude/      project skills, slash commands, shared plugin settings
.github/      PR template, CI and deploy workflows, Dependabot
```

## Team

| Person | Lane |
|---|---|
| Shaan | **Data + Core**: search, the answer pipeline, the citation verifier. Reviews and merges |
| Akash | **Platform**: API, database, sign-in, server, the upload backend |
| Meghna | **Web**: every screen people see |
| Ranveer | **Lawyers + Outreach**: interviews, the advocate, counsel, Vaquill, beta users |

Each lane owns its own folders. Details, hours and the daily standup:
[team/README.md](team/README.md).

## Documentation

### Specs (source of truth)

| Document | Date | Contents |
|---|---|---|
| [Product Requirements Document](docs/KanoonBuddy-Product-Requirements-Document.pdf) | 9 Oct 2026 | Positioning, competitor teardown, pricing, launch scope, dataset audit. 59 pp. |
| [Tech Stack](docs/KanoonBuddy-Tech-Stack.pdf) | 6 Oct 2026, rev. 9 Oct | v1 architecture, service choices, running cost, decisions D1–D6. 48 pp. |
| [System Architecture Reference (HLD + LLD)](docs/KanoonBuddy-System-Architecture-Reference-HLD-LLD.pdf) | 6 Oct 2026 | High- and low-level design |
| [Website Design Doc v2](docs/KanoonBuddy-Website-Design-Doc-v2.md) | 9 Oct 2026 | Marketing site: pages, visual system, copy rules |

**Where the PRD and the Tech Stack disagree, the Tech Stack wins** (stated in the PRD's
review key).

### Working docs

**Product**

| Document | Covers |
|---|---|
| [docs/PRODUCT.md](docs/PRODUCT.md) | Problem, goals, users, MVP scope, plans and pricing, go-to-market, naming |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phases, effort estimates, the data refresh plan |
| [docs/METRICS.md](docs/METRICS.md) | Success metrics, the launch gate, the validation plan |
| [docs/UX-COPY.md](docs/UX-COPY.md) | Failure states, badge wording, standing notices, copy rules |
| [docs/RISKS.md](docs/RISKS.md) | Combined risk register with mitigations |

**Engineering**

| Document | Covers |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Rules for coding agents: scope, the seven rules, hard limits |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | The 11-step pipeline, stack by layer, search, Jev, uploads |
| [docs/DECISIONS.md](docs/DECISIONS.md) | **Top 5 questions before any code**, plus settled and open decisions |
| [docs/DATASET.md](docs/DATASET.md) | What the corpus holds, the audit, field quality, licence, Vaquill |
| [docs/DATA-MODEL.md](docs/DATA-MODEL.md) | 17 PostgreSQL tables, 2 Qdrant collections |
| [docs/API.md](docs/API.md) | v1 routes, error format, SSE contract |
| [docs/CITATION-VERIFIER.md](docs/CITATION-VERIFIER.md) | The four checks; what the tick means and does not |
| [docs/BUILD-ORDER.md](docs/BUILD-ORDER.md) | 11 build steps and the launch gate |
| [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) | Config contract and feature switches |
| [docs/TESTING.md](docs/TESTING.md) | Must-pass list, CI, and the 200-question test set |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | Rebuild plan, backups, monitoring, release checklist, incidents |
| [docs/GLOSSARY.md](docs/GLOSSARY.md) | Every term, in plain words |
| [knowledge/index.md](knowledge/index.md) | How OKF knowledge notes work |

**Legal and compliance**

| Document | Covers |
|---|---|
| [docs/SECURITY-AND-COMPLIANCE.md](docs/SECURITY-AND-COMPLIANCE.md) | DPDP, BCI Rule 36, privilege, security, uploads |
| [docs/RETENTION.md](docs/RETENTION.md) | Retention per data type — **undecided, needs counsel** |
| [docs/BREACH-PLAYBOOK.md](docs/BREACH-PLAYBOOK.md) | The 72-hour plan — **skeleton** |
| [legal/README.md](legal/README.md) | The user-facing documents that must exist before sign-up |

**Team and planning**

| Document | Covers |
|---|---|
| [team/README.md](team/README.md) | People, lanes, first-time setup, one task per session, standup |
| [team/V1-PLAN.md](team/V1-PLAN.md) | 11 weeks to the MVP: what's in, what moved to January, the drop order |
| [team/WEEK-1.md](team/WEEK-1.md) to [WEEK-11.md](team/WEEK-11.md) | Each week on one screen; per-person detail in `team/week-N/` |
| [team/MONTH-2.md](team/MONTH-2.md) and [MONTH-3.md](team/MONTH-3.md) | Weeks 5 to 8 and 9 to 11: assumptions, decisions, outside deadlines, holidays, beta readiness |
| [.claude/README.md](.claude/README.md) | Project skills and slash commands, and which marketplace skills to use |
| [skills-used/README.md](skills-used/README.md) | Which skills were planned, used or rejected |

## Evidence labels

Facts in these docs carry one of six labels, used consistently. Keep them; do not promote
an Estimate to a fact without measuring it.

**Measured** (checked on a local copy of the dataset) · **Checked** (confirmed on a public
page, with the date) · **Dataset card** (claimed by the dataset's own pages) ·
**Competitor claim** (from a competitor's site) · **Estimate** (worked out from stated
inputs) · **Needs verification** (not confirmed, with how to confirm it)

## Getting set up

Follow the **first-time setup** in [team/README.md](team/README.md). In short: your own
Claude Code account, accept the plugins Claude Code offers when you open the repo,
`gh auth login`, and your own `.env`:

```bash
cp .env.example .env     # then fill it in — see docs/ENVIRONMENT.md
```

## How a task gets done

Every task is a GitHub issue, sized for **one Claude Code session**:

```
/start-task 12     read issue #12, make the branch, explain the plan, wait for a yes
   ... build ...
/finish-task 12    run the checks for real, open the PR ("Closes #12"), update the issue
```

Shaan reviews and merges; merging closes the issue. Nobody else pushes to `main`.

Nothing is scaffolded yet. Week 1 builds the foundations in parallel: the search
collection and the verifier's free checks (Shaan), the Python project, Docker Compose and
database (Akash), and the Next.js app and chat screen on a fake stream (Meghna). See
[team/WEEK-1.md](team/WEEK-1.md).

Before writing much code, read the **top 5 open questions** in
[docs/DECISIONS.md](docs/DECISIONS.md). Several of them are not engineering work — 20 user
interviews, a 100-judgment hand check, and conversations with counsel and with Vaquill —
and their answers change the plan.

## Status

Pre-launch. **Week 1 of 11** (13 to 17 Oct 2026). Internal targets: MVP finished by
**Sat 26 Dec 2026**, private beta from **Mon 4 Jan 2027** — see
[team/V1-PLAN.md](team/V1-PLAN.md).

Pricing, upload limits and the product name are still open; see
[docs/DECISIONS.md](docs/DECISIONS.md). Nothing here is a public commitment.

Data: Open India Law by Vaquill AI, CC BY 4.0.
