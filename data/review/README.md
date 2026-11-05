# Review pack: central Acts stored under state record ids (A152, A153)

**Status: UNREVIEWED. Nothing here is a determination.** `data/act_scope.json`, the table the
build would read, does not exist; it is written by a person after this review.

## What to review
`act_scope_candidate_groups.csv`: one row per normalised title (221 groups, 475 copies, 53,245
points). Fill the empty columns: `reviewer_verdict` (central / state / unsure), `repealed_by` if
the Act has been repealed, `reviewer_note`, `reviewed_by`, `reviewed_on`. `act_scope_candidates.csv`
lists every copy (`source_url` points at the publishing site, so the text can be checked there).

Regenerate with `.venv/bin/python data/build_act_scope_candidates.py` (read-only).

## Why a candidate is a candidate
Three signals, each a hint: **S1** title equals a central Act held in `kanoon_v1`; **S2** the same
title is republished by 3 or more states with no state name in it; **S3** territorial extent says
"the whole of India" with no state name in the title.

## Known ways the list is wrong (found by reading it, not by a test)
- **False positives.** `The PunjabCinema(Regulation)Act,1952` and `Thunchath Ezhuthachan Malayala
  University Act 2013` are state Acts that S3 caught: the state name is glued to the next word, or
  the extent clause is loose. Expect more of these among the 100 groups flagged by S3 alone.
- **One Act, several groups.** Titles are normalised, not matched by meaning: `The INDIAN-PENAL-CODE-1860`
  and `Indian Penal Code 1860` are separate groups. Merge them in your verdict.
- **86 of 221 groups (138 copies, 14,523 points) are Acts `kanoon_v1` already holds**; the other 135 groups (337 copies, 38,722 points) are not held centrally.
  For the first kind (S1 or a matching title). For them the state
  copies are duplicates of a held Act, not a missing Act: the question there is only to keep them out
  of the way, not to add them.
- **A lower bound.** An Act that no state republishes and that has no extent clause is not here.
- **Status is not in this list.** Every copy carries `act_status = in_force`, which is a default (CLAUDE.md
  section 6). The Code of Criminal Procedure 1973 and the Consumer Protection Act 1986 have both been
  replaced by later Acts (BNSS 2023 and the 2019 Act, which `kanoon_v1` holds); **unverified in the dataset;
  check against the statute**. Record `repealed_by` for every group you can.

## What a verdict does
Nothing yet. A `central` verdict would, in a later build, set `act_scope = central` on the chosen
canonical copy and fold the other copies into it (`canonical_act_id`). It never changes a record id.
