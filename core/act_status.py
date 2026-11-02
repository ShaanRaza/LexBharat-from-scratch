"""Is this Act in force, repealed, or not checked? One pure function, three answers.

Built only from facts already in the data (decisions A180, A181), never from guessing:

  repealed     ANY of: act_status says repealed; the dataset's is_repealed flag is
               true; the Act id starts with IND_REP_; the title ends with the one
               repeal marker the data uses, "(Rep., Act NN of YYYY)". Every extra
               signal moves in the SAFE direction: repealed protects a lawyer, in
               force endangers one.
  in_force     ONLY when act_status says in force, nothing above says repealed, AND
               show_in_force is switched on. It is OFF (settings.SHOW_IN_FORCE) until
               the act_status count shows that "in_force" is a measurement and
               not a default value (CLAUDE.md section 6). Off, such an Act
               reads not_checked.
  not_checked  everything else, including a title that mentions a repeal in a form we do
               not parse cleanly: unclear means unknown, never a guess either way.

What this does NOT claim: that an Act marked in force is good law today (the data is a
snapshot, v2026.08), or that a repealed marker names the right repealing Act.

Plain-Python, no outside services, no styling. Also a read-only counter:

    .venv/bin/python -m core.act_status acts.jsonl.gz     # or .jsonl / .csv / .parquet

Read-only. Needs columns act_id, title, act_status (and is_repealed if present).
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
    # Which signals fired, for the count and for audits: "act_status", "is_repealed",
    # "id_prefix", "title_marker", "title_marker_unclear", "in_force_withheld".
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


def _flag_true(value: object) -> bool:
    """is_repealed as a yes. Lenient on purpose (a CSV gives "True"): a false yes only
    makes an Act read repealed, the safe direction. None, False, "", "false": no."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"true", "t", "1", "yes", "y"}
    return False


def read_act_status(
    act_id: object,
    title: object,
    act_status: object,
    is_repealed: object = None,
    *,
    show_in_force: bool = False,
) -> ActReading:
    """The three-way answer for one Act (or any section of it: pass its record id)."""
    status = _normal_status(act_status)
    ident = act_id.strip() if isinstance(act_id, str) else ""
    name = title if isinstance(title, str) else ""

    basis: list[str] = []
    if status == "repealed":
        basis.append("act_status")
    if _flag_true(is_repealed):
        basis.append("is_repealed")
    if ident.startswith(REPEALED_ID_PREFIX):
        basis.append("id_prefix")
    if _CLEAN_MARKER.search(name):
        basis.append("title_marker")
    if basis:
        return ActReading("repealed", tuple(basis), conflict=status == "in_force")

    if status == "in_force":
        if _UNCLEAR_MARKER.search(name):
            return ActReading("not_checked", ("title_marker_unclear",))
        if not show_in_force:
            return ActReading("not_checked", ("in_force_withheld",))
        return ActReading("in_force", ("act_status",))
    return ActReading(
        "not_checked", ("title_marker_unclear",) if _UNCLEAR_MARKER.search(name) else ()
    )


def _id_kind(ident: str) -> str:
    """central / state / IND_REP_ / other, from the id alone."""
    for prefix, kind in (
        (REPEALED_ID_PREFIX, "IND_REP_"),
        ("IND_central_", "central"),
        ("IND_state_", "state"),
    ):
        if ident.startswith(prefix):
            return kind
    return "other"


def count_acts(acts, *, show_in_force: bool = False) -> dict:
    """Counts over an iterable of {act_id, title, act_status[, is_repealed]}. Each Act
    is counted once, by its first row; Acts without an id are skipped (and counted).

    `shown` is what a reader would see under the current switch. `withheld_in_force` is
    how many Acts read not_checked ONLY because the switch is off (act_status says in
    force, nothing says repealed). `act_status_values` and `by_id_kind` answer "is
    in_force a measurement or a default": if every Act of one id kind has the same
    value while the other kinds vary, that value is a default."""
    seen: set[str] = set()
    states: Counter[str] = Counter()
    signals: Counter[str] = Counter()
    values: Counter[str] = Counter()
    kinds: dict[str, Counter[str]] = {}
    flag: Counter[str] = Counter()
    conflicts = withheld = unclear = no_id = flag_missed = 0
    for a in acts:
        ident = a.get("act_id") or a.get("id")
        if not ident:
            no_id += 1
            continue
        if ident in seen:
            continue
        seen.add(ident)
        raw = a.get("act_status")
        r = read_act_status(
            ident,
            a.get("title") or a.get("act_name"),
            raw,
            a.get("is_repealed"),
            show_in_force=show_in_force,
        )
        states[r.status] += 1
        value = (
            raw.strip().lower() if isinstance(raw, str) and raw.strip() else "(empty)"
        )
        values[value] += 1
        kinds.setdefault(_id_kind(ident), Counter())[value] += 1
        if r.status == "repealed":
            for sig in r.basis:
                signals[sig] += 1
        withheld += "in_force_withheld" in r.basis
        unclear += "title_marker_unclear" in r.basis
        conflicts += r.conflict
        has = a.get("is_repealed")
        flag["true" if _flag_true(has) else "missing" if has is None else "false"] += 1
        # does the flag agree with the other three signals?
        others = [x for x in r.basis if x != "is_repealed"]
        flag_missed += r.status == "repealed" and bool(others) and not _flag_true(has)
    return {
        "acts": len(seen),
        "shown": {k: states[k] for k in ("repealed", "in_force", "not_checked")},
        "withheld_in_force": withheld,
        "repealed_by_signal": {
            k: signals[k]
            for k in ("act_status", "is_repealed", "id_prefix", "title_marker")
        },
        "is_repealed_flag": dict(flag),
        "repealed_by_other_signal_but_flag_not_true": flag_missed,
        "act_status_values": dict(values.most_common()),
        "by_id_kind": {k: dict(v.most_common()) for k, v in sorted(kinds.items())},
        "unclear_title_marker": unclear,
        "in_force_but_marked_repealed": conflicts,
        "skipped_no_id": no_id,
    }


def _rows(path: str):
    import csv
    import gzip
    import json

    if path.endswith(".parquet"):
        import pyarrow.parquet as pq  # only needed for this file type

        cols = ["act_id", "title", "act_status", "is_repealed"]
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
