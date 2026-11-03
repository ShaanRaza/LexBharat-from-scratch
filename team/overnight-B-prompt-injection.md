# Overnight lane B — prompt injection review

**Night of 3–4 Nov 2026. Read `CLAUDE.md` first, then load the `ai-security` skill and the
`upload-privacy` skill. You own `tests/security/` (new) and `docs/SECURITY-AND-COMPLIANCE.md`.
Do not touch `core/`, `data/`, `docs/DATA-GAPS.md` or `docs/DECISIONS.md` — three other
sessions are working tonight. Report findings; propose fixes in the report rather than
rewriting `core/`.**

## Why this exists

`CLAUDE.md` names this gap explicitly: user questions **and uploaded documents** reach models,
so a hostile PDF is an attack surface nobody has reviewed. This product handles advocates'
client files. An injection that works here does not leak a toy — it leaks privileged material,
or makes the product state law that no retrieved passage supports.

## No Qdrant, no Voyage, no disk-heavy reads

This is code reading and test writing. Three other sessions are using the disk tonight; stay
off it.

## The job

1. **Map every path by which text the product did not write reaches a model.** The user's
   question, conversation history, retrieved passage text from the corpus, uploaded document
   text after OCR, and knowledge notes. For each, name the file and line where it enters a
   prompt.
2. **For each path, ask what a hostile string could do.** Specifically:
   - Can text inside a *retrieved corpus passage* alter the answer step's behaviour? The
     corpus is third-party data (Open India Law), not ours.
   - Can text inside an *uploaded document* alter the gate (step 7) or the claim-support check
     (verifier check 4)? If a hostile PDF can talk the gate into passing an irrelevant
     passage, or talk check 4 into "supports", the trust promise fails silently.
   - Can injected text cause a citation to be *fabricated* rather than dropped? Checks 1–3 are
     plain Python and cannot be talked out of, which is the designed defence — confirm that
     holds by reading `core/verify.py`, and say so plainly if it does.
3. **Check the privacy boundary holds under injection.** `CLAUDE.md` §6: upload text must
   never reach Jev, Langfuse or Sentry. Can a hostile document cause upload text to be echoed
   into a place that is logged? Read the masking and scrubbing config, do not assume it.
4. **Write tests that try to break it** in `tests/security/`, in the spirit of the trust
   tests: adversarial strings as question text, as passage text, and as upload text. A test
   that cannot fail proves nothing — for each test, disable the defence it exercises, confirm
   the test fails, then restore the file and confirm it passes. Report both runs.

## What good output looks like

A findings list ranked by what an attacker actually gets, each with the file and line, a
concrete failing input, and whether it is reachable today or only after an unbuilt feature
ships. Then the tests. Say which of the 11 pipeline steps each finding touches.

**Do not weaken any verifier check to make a test pass.** If a check blocks your test, that is
the check working. Report it as a positive finding.

## Report

Findings into `docs/SECURITY-AND-COMPLIANCE.md` under a new dated section, tests into
`tests/security/`, commit locally. Run `.venv/bin/pytest tests/trust` and show the output.
Do not push if the rebase is not clean — say so and leave it.
