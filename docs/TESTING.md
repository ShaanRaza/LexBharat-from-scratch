# Testing

Rule 6 of the seven: **tests guard the trust promise.** The citation verifier and the usage
meter have tests that must pass before any deploy. The 200-question test set runs on every
release.

## Three layers

| Layer | What it covers | When it runs |
|---|---|---|
| Unit tests | Verifier checks 1–3, usage meter, chunk offsets, the shared upload data-access function, adapters (mocked) | Every push |
| Integration tests | Pipeline end to end against a small fixture collection; SSE ordering; Razorpay webhook signature | Every push |
| The 200-question test set | Real questions, scored for verified citations, correctness, cost and speed | **Every release**, from the admin page |

## Must-pass before any deploy

- [ ] Each of the four verifier failure reasons removes the citation **and** logs it:
      `not_retrieved`, `record_missing`, `quote_not_found`, `claim_not_supported`
- [ ] A case the model names but that was **not** in S1–S8 is removed (check 1)
- [ ] Checks 1–3 still run with **Jev switched off** and with Jev timing out
- [ ] No citation-shaped content is emitted before the single post-verification `citations`
      event
- [ ] The usage meter counts one answer per non-cached answer, and **zero** for cache hits
- [ ] The usage check runs **before** any AI call and stops at the limit with a clear error
- [ ] Every `user_documents` query carries a `user_id` filter — assert at the data-access
      function, and fail the build if any other module queries that collection
- [ ] Hard delete removes the S3 object, the PostgreSQL text **and** the Qdrant vectors
- [ ] The not-legal-advice notice and the data-as-of date are present on every answer,
      stats page and Act page
- [ ] No secret appears in any log line, Langfuse trace or Sentry payload

## The 200-question test set

Lives in [`../evals/`](../evals/) with its scorer. **Frozen**, so results compare release
to release, and **signed off by the advocate advisor before it is used**.

| Part | Count |
|---|---|
| Real questions collected in the validation interviews | 100 |
| Act and section lookups | 50 |
| **Traps** — cases that do not exist, wrong section numbers, events after the snapshot date | **50** |

> **Current structure (A101, a starting point):** the set in `evals/question_set.jsonl` is split by what each question tests (answerable, out of scope, nothing found, personal advice, Rule 36, fabricated citations, name bait, in-force bait, injection), not by the 100/50/50 above. **100 of its 200 rows are stubs awaiting an advocate's labels and count as NOT RUN, never as passes.** The table above is the original plan.

The 50 traps are what prove the verifier and the out-of-scope detection actually work.
**Do not drop them to raise the score.**

| Metric | Target |
|---|---|
| **Verified-citation rate** | **≥ 98%** — launch gate condition (a) |
| Answers with a removed citation (any of the four reasons) | **< 0.5%** |
| Confirmed fabricated citations reaching a user | **zero** — launch gate condition (c) |
| First word | under 3 s |
| Full answer | under 20 s |
| Search stage | under 800 ms |
| Cost per answer | tracked in Langfuse, compared against the Estimate |

The set is also how every threshold gets set rather than guessed: the **Jev gate threshold
(0.6 to start)**, and each `JEV_ENABLED_*` switch, which turns on for users **only once it
beats the version without it**.

Full metric definitions and owners: [METRICS.md](METRICS.md).

## Continuous integration

GitHub Actions runs on every push (`.github/workflows/`). **Never deploy from a laptop** —
Actions deploys to the server.

> **Before adding the first workflow:** the GitHub token in use must have the `workflow`
> scope, or the push is rejected. Re-authorise with
> `gh auth refresh -h github.com -s workflow`, or add the workflow through the GitHub web
> UI once.

| Workflow | Job | Runs | State today |
|---|---|---|---|
| `ci.yml` | **hygiene** — `.env` not committed, Markdown links resolve | Every push and PR | Active |
| `ci.yml` | **python** — ruff lint, format check, pytest | Every push and PR | Skips until `pyproject.toml` exists (build step 2) |
| `ci.yml` | **web** — lint, `tsc --noEmit`, build | Every push and PR | Skips until `web/package.json` exists (build step 4) |
| `deploy.yml` | Deploy to the Mumbai server | **Manual dispatch only** | Skeleton — steps commented out until build step 6 |
| `dependabot.yml` | Dependency updates | Weekly | **github-actions only.** pip, npm and docker are commented out — Dependabot **errors** on a missing manifest rather than finding nothing. Uncomment each as its manifest lands |

The detect-then-skip pattern is deliberate: CI that is red from day one gets ignored. Each
job turns itself on when its manifest appears.

The **200-question test set** runs separately, from the admin page, on every release — not
in CI, because it costs real money per run.

## Separate hand checks (not automated)

| Check | Gate |
|---|---|
| **50-judgment Supreme Court hand check** of outcome labels | Supreme Court stats go live only if it passes, against a pass rule **agreed with the advocate before checking** |
| Advocate review of knowledge notes | Only `status: reviewed` notes are used in live answers |
| Independent security test | Launch gate condition (e) |
| Advocate's written legal opinion | Launch gate condition (d) |
| 20 real court scans | Sets the OCR quality threshold and the upload size/page limits |
| Week-1 test on 50 real questions | Picks the model per plan; decides whether model routing turns on |
