# Overnight lane C — rewrite the launch gate, and switch on the HC citation work

**Night of 3–4 Nov 2026. Read `CLAUDE.md` first. You own `docs/PRD-v2.md` §7 and the config
change in item 2. Do not touch `core/` beyond the one config value, `data/`,
`docs/DATA-GAPS.md` or `docs/DECISIONS.md` — three other sessions are working tonight. No
Qdrant, no Voyage, no disk-heavy reads.**

## Item 1 — the launch gate is written for a product that no longer exists

`CLAUDE.md` §1 says so directly: the owner widened v1 to the full product on 3 Nov (A124), and
`PRD-v2.md` §7's gate was written for the MVP. Rewrite it against full scope.

What changed that the gate must now cover:

- **All High Courts**, not three. So the Kerala work, the per-court embedding-model config
  (A128) and the `court`-from-id derivation are gate items, not deferrable ones.
- **State Acts and regulators**, whose BM25 sparse vectors are repaired in
  `acts_noncentral_v1` (A133) and must be promoted into the launch collection.
- **Tribunals are not in the dataset at all** and depend on an external party. The gate must
  state explicitly whether launch waits on them. **That is the owner's decision — do not
  decide it.** Write it as a named open question with both branches spelled out.
- **The 200-question eval set** was written for the narrow corpus and needs High Court and
  tribunal questions (A101, A103), which grows the advocate's labelling job.
- **Measurements that do not exist yet** and that the gate should require before launch:
  retrieval quality on the real corpus, the §10 latency targets measured on the real server
  (a single Voyage query embed measured 1.14 s p50 on a laptop, above the whole 800 ms search
  target — see A131), and A128's net quality effect.
- **Open rows that must close before launch**, read from `docs/DECISIONS.md` rather than from
  this file, since other sessions are adding rows tonight.

Keep every existing gate item that still applies. **Do not quietly drop a requirement to make
the gate reachable** — if an item now looks unachievable, say so in the gate and leave it.

## Item 2 — switch on the neutral-citation work

A124 and A125 are built and tested but marked NOT DEPLOYED. High Courts have **no citation
strings at all** (0.0% filled), so until this is on, a High Court answer shows a case with no
citation. Read both rows, then enable it through config, not by editing logic.

Two constraints that are not yours to decide:

- The `CASE_REFERENCE_LABEL` wording is reserved to the owner (`CLAUDE.md` §8 — it changes
  what a user is told about the law). Leave whatever placeholder the rows specify and name the
  question in your report.
- `.venv/bin/pytest tests/trust` must pass afterwards, and show the output. If enabling it
  changes what the verifier accepts, stop and report instead of proceeding.

## Report

Commit locally. Do not push if the rebase is not clean — say so and leave it. End with the
list of questions the gate now puts to the owner, shortest first.
