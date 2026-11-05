# Advocate review pack: who is speaking the supporting words

Built 5 Nov 2026 by the trust lane. Why it exists: `docs/DATA-GAPS.md` sections 22 and 25. It replaces the generic
Supported / Partly / Not-supported task for these pairs, which the owner has removed from the advocate brief.

## What it is

Two Excel workbooks, one per advocate, made by `python -m evals.labelling.build_speaker_pack --pairs <pairs.json> --out-dir <dir>`
(builder: `evals/labelling/build_speaker_pack.py`; tests: `tests/test_speaker_pack.py`, mutation-checked: a leaked verdict, flagged
pairs not shared, pairs dropped, and no shuffle each fail a test).

- **79 pairs**, the (sentence, cited passage) pairs of the A137 new-prompt run. The passage is shown in full as the writer saw it.
- **20 shared pairs** appear in both workbooks (the 9 the hand reading flagged, 11 at random). The other 59 go to one advocate each: **A 50 rows, B 49 rows.**
- **One closed question per row, nine answers** (list in section 22 of DATA-GAPS). Nothing the system concluded is in any cell: not the hand reading, not the real claim check, not the stratum. Row order is shuffled with a fixed seed.
- Files are written **outside the repo** (`advocate-review-pack/`, next to the repo folder): they hold judgment text and party names.
- The input `pairs.json` is not in the repo either. It is rebuilt from the A137 harness output (`new3.json` in the trust lane's scratch space); say if it should be kept somewhere durable.

## Reading load: measured as words, time not yet measured

| | Rows | Words per row, median | p90 | max | Total words |
|---|---|---|---|---|---|
| Advocate A | 50 | 635 | 726 | 762 | 26,886 |
| Advocate B | 49 | 636 | 726 | 762 | 25,278 |

Words are question + sentence + passage. The passage dominates, so rows are uniformly long (about 600 to 760 words).

**Time: not measured.** The pack carries a "Time test" sheet naming ten rows to time. I have not timed a person and cannot. An **Estimate**
of reading time alone, at 150 to 250 words a minute for dense legal prose: **1.8 to 3.0 hours per advocate**, before any deciding or writing a note. The
honest number is the median of the advocate's ten timed rows times 50. Do not quote hours before that.

## Scoring and what it gives

Correct: the court, or the statute quoted by the court. Misattributed (the 6.3% class): a party, a rejected argument, a lower court, another authority,
an order on the facts. Unsupported: nobody. Undecided: reported beside the figure. The figure: misattributed over reviewed, with a Wilson interval, plus the by-answer figure. Next
to it, the real claim check's result on the same pairs (section 22): it passed all 5 pairs the hand reading flagged.
