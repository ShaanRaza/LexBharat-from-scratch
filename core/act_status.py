"""Is this Act in force, repealed, or not checked? One pure function, three answers.

Built only from facts already in the data (decision A180), never from guessing:

  repealed     ANY of: act_status says repealed; the Act id starts with IND_REP_; the
               title ends with the one repeal marker the data uses,
               "(Rep., Act NN of YYYY)".
  in_force     ONLY when act_status says in force (and nothing above says repealed).
  not_checked  everything else, including a title that mentions a repeal in a form we do
               not parse cleanly: unclear means unknown, never a guess either way.

What this does NOT claim: that an Act marked in force is good law today (the data is a
snapshot, v2026.08), or that a repealed marker names the right repealing Act.

Plain-Python, no outside services, no styling. Also a read-only counter:

    .venv/bin/python -m core.act_status acts.jsonl.gz     # or .jsonl / .csv / .parquet
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Literal

ForceStatus = Literal["in_force", "repealed", "not_checked"]

REPEALED_ID_PREFIX = "IND_REP_"

# The one marker form seen in the data: "... Act, 1872 (Rep., Act 47 of 2023)".
# It must be the last thing in the title, with a 4-digit year in a sane range.
_CLEAN_MARKER = re.compile(
    r"\(Rep\.,\s+Act\s+\d{1,4}\s+of\s+(?:1[6-9]\d\d|20\d\d)\)\s*\.?\s*$"
)
# Anything else that looks like a repeal note ("(Rep. by Act 5 of 2001)", "(Repealed)"):
# real, perhaps, but not parsed cleanly, so it can only make the answer "not checked".
_UNCLEAR_MARKER = re.compile(r"\brep\.|\brepealed\b", re.IGNORECASE)


@dataclass(frozen=True)
class ActReading:
    status: ForceStatus
    # Which signals fired, for the count and for audits: "act_status", "id_prefix",
    # "title_marker", "title_marker_unclear".
    basis: tuple[str, ...]
    # True when act_status said in force but another signal said repealed: reported
    # so the owner can see how often the two disagree. The answer is still "repealed".
    conflict: bool = False


def _normal_status(value: object) -> Literal["in_force", "repealed"] | None:
    """act_status as one of the two values we act on; 'spent' and the rest: None."""
    if not isinstance(value, str):
        return None
    s = re.sub(r"[\s_\-]+", " ", value.strip().lower())
    if s == "in force":
        return "in_force"
    if s == "repealed":
        return "repealed"
    return None


def read_act_status(act_id: object, title: object, act_status: object) -> ActReading:
    """The three-way answer for one Act (or any section of it: pass its record id)."""
    status = _normal_status(act_status)
    ident = act_id.strip() if isinstance(act_id, str) else ""
    name = title if isinstance(title, str) else ""

    basis: list[str] = []
    if status == "repealed":
        basis.append("act_status")
    if ident.startswith(REPEALED_ID_PREFIX):
        basis.append("id_prefix")
    if _CLEAN_MARKER.search(name):
        basis.append("title_marker")
    if basis:
        return ActReading("repealed", tuple(basis), conflict=status == "in_force")

    if status == "in_force":
        if _UNCLEAR_MARKER.search(name):
            return ActReading("not_checked", ("title_marker_unclear",))
        return ActReading("in_force", ("act_status",))
    return ActReading(
        "not_checked", ("title_marker_unclear",) if _UNCLEAR_MARKER.search(name) else ()
    )


def count_acts(acts) -> dict:
    """Counts for the three states over an iterable of {act_id, title, act_status}.
    Each Act is counted once, by its first row; Acts without an id are skipped."""
    seen: set[str] = set()
    states: Counter[str] = Counter()
    basis: Counter[str] = Counter()
    conflicts = no_id = 0
    for a in acts:
        ident = a.get("act_id") or a.get("id")
        if not ident:
            no_id += 1
            continue
        if ident in seen:
            continue
        seen.add(ident)
        r = read_act_status(
            ident, a.get("title") or a.get("act_name"), a.get("act_status")
        )
        states[r.status] += 1
        if r.status == "repealed" or r.basis == ("title_marker_unclear",):
            for b in r.basis:
                basis[b] += 1
        conflicts += r.conflict
    return {
        "acts": len(seen),
        "in_force": states["in_force"],
        "repealed": states["repealed"],
        "not_checked": states["not_checked"],
        "repealed_by_signal": {
            k: basis[k] for k in ("act_status", "id_prefix", "title_marker")
        },
        "unclear_title_marker": basis["title_marker_unclear"],
        "in_force_but_marked_repealed": conflicts,
        "skipped_no_id": no_id,
    }


def _rows(path: str):
    import csv
    import gzip
    import json

    if path.endswith(".parquet"):
        import pyarrow.parquet as pq  # only needed for this file type

        cols = ["act_id", "title", "act_status"]
        yield from pq.read_table(path, columns=cols).to_pylist()
        return
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        if ".csv" in path:
            yield from csv.DictReader(f)
        else:
            for line in f:
                if line.strip():
                    yield json.loads(line)


if __name__ == "__main__":
    import json

    if len(sys.argv) != 2:
        sys.exit("usage: python -m core.act_status <file.jsonl[.gz]|.csv|.parquet>")
    print(json.dumps(count_acts(_rows(sys.argv[1])), indent=2))
