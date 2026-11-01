# Agent team: how to start (paste into Claude Code, in the repo folder)

Before you start: `git checkout shan/agent-team`, and make sure
`.claude/settings.local.json` contains:

```json
{ "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }
```

(That file is git-ignored, so it only affects your computer.)

## Prompt for the lead

```
Read CLAUDE.md fully (especially §2 seven rules, §5 verifier, §6 hard rules, §12 lanes),
docs/BUILD-ORDER.md, docs/ARCHITECTURE.md and docs/DECISIONS.md first.

Create an agent team of 4 teammates for LexBharat v1, working on branch shan/agent-team.
Each teammate owns ONLY its folders (CLAUDE.md §12) and never edits another teammate's
files. Only you (the lead) edit CLAUDE.md, pyproject.toml and docs/DECISIONS.md.

1. core-data: core/, adapters/, evals/, tests/core/. Adapters with fakes (one file per
   vendor), one function per pipeline step, citation verifier checks 1-3 with tests,
   eval runner. No real API keys; use fakes.
2. platform: api/, migrations/, workers/, infra/, .github/, tests/api/. Alembic
   migrations for the 17 tables in docs/DATA-MODEL.md, FastAPI routes from docs/API.md,
   Docker Compose (check ARM builds), CI.
3. web: web/ only (Meghna's Next.js scaffold is already there). Chat screen with
   per-citation ticks, failure screens, Act and judgment pages. Talks to the backend
   only through the API (fake mode for now).
   Design rule for this and all future work: keep the current look, but make it easy to reskin later.
   - All colors, fonts, sizes, spacing and radii come from shared design tokens in one file. No hard-coded colors or fonts in components.
   - Reuse shared components (search bar, buttons, cards, citation chips, labels, sidebar, top bar) instead of styling each page separately.
   - Keep UI separate from logic: search, chat, drafting and review logic must not depend on styling.
   - If you find existing hard-coded colors or fonts in files you touch, move them to tokens.
4. reviewer: read-only. When the others finish, run all tests and check the work
   against the seven rules and hard rules. Report problems; do not fix them.

Rules for everyone: small commits; run tests before saying done; write "not verified"
for anything not actually run; record each non-obvious decision in your report so the
lead can add it to docs/DECISIONS.md. Stop and ask me before anything in CLAUDE.md §12
"Still the owner's call".
```
