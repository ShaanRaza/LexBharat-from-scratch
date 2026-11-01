# Agent team: how to start (paste into Claude Code, in the repo folder)

Before you start: `git checkout shan/agent-team`, and make sure
`.claude/settings.local.json` contains:

```json
{ "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }
```

Do not start Claude Code with `--dangerously-skip-permissions`.

## Prompt for the lead

```
Read CLAUDE.md fully first (especially §2 seven rules, §5 verifier, §6 hard rules, §12 lanes), then docs/BUILD-ORDER.md, docs/ARCHITECTURE.md, docs/DECISIONS.md and docs/AGENT-TEAMS.md.

Create an agent team (not subagents) of 5 teammates named core, trust, platform, web and reviewer, for LexBharat v1, on branch shan/agent-team. Commit there. Never push to main. Only you (the lead) open the pull request and edit CLAUDE.md, pyproject.toml and docs/DECISIONS.md. Each teammate owns ONLY the folders in CLAUDE.md §12 and never edits another teammate's files. About 5 tasks each. Wait for all teammates to finish before you summarise; do not do their work yourself.

ORDER (create these as task dependencies):
1. core writes core/contracts.py FIRST: the shared types (pipeline request, result, citation with status verified/partly, outcomes) and the one entry point run_pipeline(request, deps). platform writes api/schemas.py FIRST: request/response shapes and the SSE events (token, citations, done, error), including for each citation: kind (judgment or act), anchor, act_slug, section, url, status. Both are done before anything else depends on them.
2. web's API client waits for platform's schemas. platform's bridge between the API and run_pipeline waits for core's contracts. trust waits for core's contracts. web can start tokens, shared components and fake data straight away.
3. reviewer reviews each task as it is completed, not only at the end.

core: core/ except verify.py and gate.py, adapters/, tests/core/. One adapter file per vendor (Voyage, Gemini, Jev, Firebase, S3, Razorpay, OCR, Qdrant), each with a Protocol and an in-memory Fake, Jev with its Gemini fallback. One separate function per pipeline step (CLAUDE.md §4; search 50, re-rank 10, at most 8 passages S1-S8). The one shared function that always adds the user_id filter to upload queries. No real API keys: fakes only.

trust: core/verify.py, core/gate.py, evals/, tests/trust/. The citation verifier checks 1 to 3 (plain Python, always run) and check 4 (through the Jev adapter), and the gate (threshold 0.6). The verifier must be impossible to skip: show() accepts only a verifier-sealed answer. Write tests that try to BREAK it: invented citation, real case not retrieved this turn, wrong quote, quote with changed spaces or punctuation, Jev down. An answer never shows a tick for an unchecked citation. Eval runner for the 200-question set with a small sample.

platform: api/, migrations/, workers/, infra/, .github/, tests/api/, tests/migrations/, tests/integration/. Alembic migrations for the 17 tables in docs/DATA-MODEL.md (numbered, reversible; test against a real Postgres if one is available). FastAPI routes from docs/API.md (routes only). Firebase login check that fails closed. CORS for the web origin. The bridge from the API to core's run_pipeline, with a clearly flagged fake mode that is never on in production. Docker Compose with ARM-compatible images (check every image), CI. An end-to-end test: question, streamed tokens, ONE citations event, done.

web: web/ only (Meghna's Next.js scaffold is already there; read web/AGENTS.md and node_modules/next/dist/docs/ first). Chat screen with a tick per citation (tick only when status is exactly "verified"), failure screens (not found, outside coverage, usage limit, service error), Act page, judgment view with paragraph anchors, sign-up with consent notice. Talks to the backend only through the API; fake mode for now.
Design rule for this and all future work: keep the current look, but make it easy to reskin later.
- All colors, fonts, sizes, spacing and radii come from shared design tokens in one file. No hard-coded colors or fonts in components.
- Reuse shared components (search bar, buttons, cards, citation chips, labels, sidebar, top bar) instead of styling each page separately.
- Keep UI separate from logic: search, chat, drafting and review logic must not depend on styling.
- If you find existing hard-coded colors or fonts in files you touch, move them to tokens.

reviewer: read-only, edits nothing. Checks each finished task against CLAUDE.md §2 (seven rules), §5 (verifier), §6 (privacy, no judge or party names, secrets). Runs the tests itself and reports with file and line. Also checks the trust promise: can any path show a citation tick that was not verified?

Rules for everyone: small commits; run the tests and show the output before saying done; write "not verified" for anything not actually run; say which of the 11 pipeline steps a change touches; never print .env or any secret; report each non-obvious decision in one line so the lead can add it to docs/DECISIONS.md. Do not decide anything in CLAUDE.md §8 "Still the owner's call"; put the question in your report.
```
