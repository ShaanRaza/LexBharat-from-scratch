"""Acts that stay OFF until an advocate fills in `repealed_by` (A182, lane D).

Plain words. Three central Acts exist in the dataset only as copies published by state or UT
websites under `IND_state_*` ids: the Code of Criminal Procedure 1973, the Payment of Gratuity Act
1972 and the Consumer Protection Act 1986. Each has since been replaced by a later Act, but the
dataset's `act_status` is a default ("in_force" on every row), so the data cannot say so. Serving
them without that fact would show a replaced Act as live law. So the code path exists, and it
refuses to emit a single record until the entry in `data/review/supplement_hold.json` carries
`repealed_by`, `reviewed_by` and `reviewed_on` (all non-empty) AND `serve` is true. Nothing here
reads Qdrant, calls a vendor, or writes anywhere; `to_supplement_record` is a pure function on a
payload dict that a later, separately approved job would feed from a copy collection.

    from data.supplement_hold import load_hold, records_for
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path

HOLD_FILE = Path(__file__).with_name("review") / "supplement_hold.json"
REQUIRED = ("repealed_by", "reviewed_by", "reviewed_on")
PREFIX = "IND_SUPP_"


class HeldBack(Exception):
    """Raised instead of producing a record for an Act whose review is incomplete."""


def load_hold(path: Path = HOLD_FILE) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["acts"]


def missing_review(entry: dict) -> list[str]:
    """What an advocate still has to supply. Empty list AND serve=true is the only way through."""
    gaps = [k for k in REQUIRED if not str(entry.get(k) or "").strip()]
    if entry.get("serve") is not True:
        gaps.append("serve (must be true; the owner switches it, not the advocate)")
    return gaps


def servable(entry: dict) -> bool:
    return not missing_review(entry)


def to_supplement_record(payload: dict, entry: dict) -> dict:
    """A copy point (from an `IND_state_*` Act) as a supplement-style record. Refuses unless the
    entry is fully reviewed. The hosting state's name is dropped from `state` because the Act is
    central, and the replacement fact is stored, not implied."""
    gaps = missing_review(entry)
    if gaps:
        raise HeldBack(f"{entry.get('slug')}: not reviewed ({', '.join(gaps)})")
    out = dict(payload)
    old_act = str(payload.get("act_id", ""))
    suffix = str(payload.get("chunk_id", "")).removeprefix(old_act).lstrip("_")
    out.update(
        act_id=f"{PREFIX}{entry['slug']}",
        chunk_id=f"{PREFIX}{entry['slug']}_{suffix}"
        if suffix
        else f"{PREFIX}{entry['slug']}",
        state="central",
        jurisdiction="central",
        category="central",
        act_status="repealed",
        section_status="repealed",
        is_repealed=True,
        repealed_by=entry["repealed_by"],
        reviewed_by=entry["reviewed_by"],
        reviewed_on=entry["reviewed_on"],
        source_kind="dataset_copy",
        copied_from_act_id=old_act,
        as_of_basis="dataset snapshot v2026.08",
    )
    return out


def records_for(entry: dict, payloads: Iterable[dict]) -> Iterator[dict]:
    """Yield nothing for a held Act. Yielding is an all-or-nothing decision per Act."""
    if not servable(entry):
        return
    only = set(entry.get("canonical_act_ids") or [])
    for p in payloads:
        if not only or p.get("act_id") in only:
            yield to_supplement_record(p, entry)
