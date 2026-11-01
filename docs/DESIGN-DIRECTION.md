# Design direction (draft for the owner — nothing here is approved yet)

Written 2 Nov 2026 so five screens are built against one decision instead of five
improvisations. The owner reviews this **on localhost**, not on paper: everything below is a
starting point to react to.

Status: **DRAFT.** No wording in section 6 is approved. `core/coverage.json` keeps
`sentence_approved: false` until the owner says otherwise, on screen.

---

## 1. What we take from Harvey, and what we do not

The owner asked for a front end that feels like Harvey. Split into two things:

**Take — these are ordinary interface vocabulary and nobody owns them:** the calm,
uncluttered, content-first layout; generous whitespace; thin line icons; a near-neutral
palette; type doing the work instead of colour; a left sidebar of spaces; a centred ask box;
the source open beside the answer; a live progress panel; task cards; accept-or-dismiss
suggestions.

**Do not take:** the wordmark, the serif logotype treatment, exact colour values, exact page
compositions, their copy. That is trade dress, and a trademark search on LexBharat is
pending (O8). Being visually confusable with the market leader is a bad fact to hold while
that search runs.

**Three reasons a straight copy would also be wrong for this product, regardless of risk:**

1. Harvey is built for partners at large firms on large screens. This is built for solo
   advocates and law students in India, often on a mid-range phone. **375px is the design
   width here, not an afterthought.**
2. Hindi comes after the launch gate. A typeface chosen today with no Devanagari sibling is
   a rebuild later.
3. The per-citation tick is this product's whole differentiator and Harvey has no equivalent,
   so there is nothing to copy for the single most important element on the page.

## 2. Type

| Role | Family | Why |
|---|---|---|
| Headings, wordmark | Noto Serif | Serious without being ornamental; has a real Devanagari sibling |
| Interface and body | Inter | Clear at small sizes on cheap screens |
| Hindi, after the gate | Noto Sans / Noto Serif Devanagari | Chosen now so Hindi is a token swap, not a redesign |

Answer text is the longest reading on the site: 16px minimum on phones, line height 1.6,
measure capped around 68 characters. Legal prose is dense enough without a wide measure.

## 3. Colour

Near-neutral and warm. The page should feel like paper, not a dashboard.

| Token | Value | Use |
|---|---|---|
| `--bg` | `#FAFAF9` | Page. Warm off-white, easier than pure white for long reading |
| `--surface` | `#FFFFFF` | Cards, the source pane |
| `--text` | `#1C1917` | Body |
| `--text-muted` | `#57534E` | Labels, dates, the credit line |
| `--border` | `#E7E5E4` | Hairlines; borders do the separating, not shadows |
| `--accent` | `#1E3A5F` | Ink blue. Links, focus rings, the primary button. Used sparingly |
| `--warn` | `#92400E` | A removed citation, a failed check. Muted, never alarming |

Dark mode is not in v1. The tokens are structured so it can be added later without touching
components.

## 4. The verification tick — the one element worth arguing about

**The tick must not be a green check.** CLAUDE.md §5 is emphatic that the tick does *not*
mean the case is good law, is not a view on whether the AI's summary is right, and is not a
promise the link works. A green check mark is universally read as approval, which is exactly
the misreading the whole document exists to prevent. Colour would quietly undo the care taken
everywhere else.

So the tick is **text-led and neutral**: a small outline mark in `--text-muted`, immediately
followed by the words "Record found in dataset" and the data-as-of date. Per citation, never
one badge for the whole answer. A removed citation uses `--warn` and says what failed.

If the owner wants colour here, that is their call — but it should be a deliberate decision,
not a default.

## 5. Spacing, density, motion

4px base scale. Sidebar 240px on desktop, a sheet on phones. The source pane sits beside the
answer only at the large breakpoint and stacks below it under that. No shadows except on
things that genuinely float. Motion only where it carries meaning — the progress panel's step
changes — at 150ms or less, and nothing at all under `prefers-reduced-motion`.

## 6. Draft wording — NOT APPROVED, for the owner to react to on screen

Everything about the law, advice, coverage or BCI Rule 36 is the owner's (CLAUDE.md §8).
These are drafts so the screens are not built around placeholder text.

| Where | Draft |
|---|---|
| Coverage sentence | "LexBharat covers Supreme Court judgments and the Acts listed on our coverage page. It does not include High Courts, district courts, tribunals, or anything after the data-as-of date." |
| Nothing found | "Not in our dataset. That does not mean it does not exist — it means our snapshot does not hold it." |
| Share refused | "This answer used your own uploaded file or saved case notes, so it cannot be shared by link." |
| Share note | "Anyone with this link can read this answer. It does not show your name." |
| Link not available | "This link is not available. It may have been switched off or expired." |
| Matter delete failed | "The matter was kept. One or more files could not be deleted, so nothing was removed." |
| In-force unknown | "In-force status not checked for this Act." |

Interface labels (buttons, headings, menu items) are not legal wording and the web lane may
write them.

## 7. How this gets reviewed

The owner runs the dev server and reacts to real screens. The fakes must be realistic first
(A57, web lane step 1) — a layout judged against three short fake passages tells you nothing
about eight real citations and a 200-character Act title.
