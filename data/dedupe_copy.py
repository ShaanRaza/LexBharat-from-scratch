"""A126's dedup rule for the copy step: drop a DEAD copy of a chunk where a live copy exists, keep both live copies.

Plain words: the original collections hold some chunk ids on two or more points (loading
duplicated them). The rule (A126, amended 3 Nov 2026):

  * one copy is dead (its dense vector is not an embedding of its text) and a live copy exists:
    DELETE the dead copy. Nothing is lost: the text and payload are identical across copies.
  * every copy is live: KEEP ALL. Where they came from different models (211 of 211 sampled
    Kerala live pairs, and Orissa and Madhya Pradesh) nothing free says which copy is which, so
    any pick discards the copy that matches the query model about half the time. A71
    (core/dedupe.py) already collapses them to one passage before re-rank.
  * anything unclear: KEEP ALL. The script only ever deletes when it is sure, and never the last
    copy.

How a dead copy is recognised. Not by the detector alone (its score falls with chunk length, and
about 1% of long healthy vectors fall under its line: DATA-GAPS section 13). The test is the
copies AGREEING WITH EACH OTHER: a dead copy sits at cosine below 0.5 to its live twin (298 of
298 measured pairs) while two live copies sit at 0.90 or more (211 of 211). The detector only
chooses WHICH of the two disagreeing copies is the dead one, and only if it is clearly lower and
under its line.

Pipeline step touched: step 5 (Search): fewer candidate points. Writes go to the COPY instance
only (port 7333), never to legal_corpus_v1, legal_corpus_v2 or acts_india. Dry run by default;
--apply writes, after saving every deleted point (payload and vectors) to a backup file so a
delete can be undone by upserting its lines.

    python data/dedupe_copy.py kanoon_v1            # report only
    python data/dedupe_copy.py kanoon_v1 --apply    # delete the dead copies, verify, keep a backup
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
DIRECTION = REPO / "data" / "dead_vectors" / "legal_direction.npy"
COPY = "http://127.0.0.1:7333"
FORBIDDEN = {"legal_corpus_v1", "legal_corpus_v2", "acts_india"}  # the originals
BACKUP = Path.home() / "qdrant-kanoon" / "dedupe"

DISAGREE_BELOW = (
    0.5  # a copy agreeing with no other copy above this is a candidate dead copy
)
AGREE_AT_LEAST = (
    0.5  # the copies that stay must agree with one another at least this much
)
DETECTOR_DEAD_BELOW = 0.10  # the dead copy must also be under the detector's line
MIN_SCORE_MARGIN = 0.03  # and clearly lower than the live copy's score


@dataclass(frozen=True)
class Member:
    id: int
    vector: np.ndarray  # the dense vector, any scale
    score: float  # the detector score of that vector


@dataclass
class GroupPlan:
    status: str  # single | dead_removed | all_live | unclear
    delete: tuple[int, ...] = ()
    keep: tuple[int, ...] = ()
    why: str = ""


def detector_score(vector: np.ndarray, direction: np.ndarray) -> float:
    v = np.asarray(vector, dtype=np.float64)
    return float(v @ direction / np.linalg.norm(v))


def _cosines(members: list[Member]) -> np.ndarray:
    m = np.array(
        [x.vector / np.linalg.norm(x.vector) for x in members], dtype=np.float64
    )
    return m @ m.T


def plan_group(members: list[Member]) -> GroupPlan:
    """The decision for ONE chunk id. Never deletes the last copy, and never deletes unless
    exactly one copy disagrees with all the others and those others agree with each other."""
    ids = tuple(m.id for m in members)
    if len(members) == 1:
        return GroupPlan("single", (), ids)
    cos = _cosines(members)
    n = len(members)
    if n == 2:  # a pair: each copy disagrees with "the others" (the one other), so the
        # copies themselves must say whether they agree, and the detector which one is dead
        if cos[0, 1] >= DISAGREE_BELOW:
            return GroupPlan("all_live", (), ids, "the two copies agree")
        dead, live = sorted(members, key=lambda m: m.score)
        if dead.score >= DETECTOR_DEAD_BELOW:
            return GroupPlan(
                "unclear",
                (),
                ids,
                f"the two disagree but neither scores under {DETECTOR_DEAD_BELOW}",
            )
        if live.score - dead.score < MIN_SCORE_MARGIN:
            return GroupPlan(
                "unclear", (), ids, "the detector does not clearly separate the two"
            )
        return GroupPlan(
            "dead_removed",
            (dead.id,),
            (live.id,),
            "the copies disagree and one scores clearly lower",
        )
    np.fill_diagonal(cos, -1.0)
    loners = [i for i in range(n) if cos[i].max() < DISAGREE_BELOW]  # agree with nobody
    if not loners:
        return GroupPlan("all_live", (), ids, "every copy agrees with another")
    if len(loners) > 1:
        return GroupPlan(
            "unclear", (), ids, f"{len(loners)} copies agree with no other"
        )
    d = loners[0]
    rest = [i for i in range(n) if i != d]
    if (
        len(rest) > 1
        and min(cos[a, b] for a in rest for b in rest if a < b) < AGREE_AT_LEAST
    ):
        return GroupPlan(
            "unclear", (), ids, "the copies that would stay disagree with each other"
        )
    dead, live_low = members[d], min(members[i].score for i in rest)
    if dead.score >= DETECTOR_DEAD_BELOW:
        return GroupPlan(
            "unclear",
            (),
            ids,
            f"the odd copy scores {dead.score:.3f}, not under {DETECTOR_DEAD_BELOW}",
        )
    if live_low - dead.score < MIN_SCORE_MARGIN:
        return GroupPlan(
            "unclear", (), ids, "the detector does not clearly separate the odd copy"
        )
    return GroupPlan(
        "dead_removed",
        (dead.id,),
        tuple(members[i].id for i in rest),
        "one copy disagrees with the rest and scores clearly lower",
    )


@dataclass
class Plan:
    groups: int = 0
    statuses: collections.Counter = field(default_factory=collections.Counter)
    delete: list[int] = field(default_factory=list)
    unclear: list[tuple[str, str]] = field(default_factory=list)  # (chunk id, why)
    identical_live_pairs: int = (
        0  # live groups whose copies are the SAME vector (a possible later saving)
    )
    delete_chunk: dict[int, str] = field(default_factory=dict)


def plan_collection(groups: dict[str, list[Member]]) -> Plan:
    """`groups`: chunk id -> its members, only for chunk ids on more than one point."""
    out = Plan()
    for cid, members in groups.items():
        p = plan_group(members)
        out.groups += 1
        out.statuses[p.status] += 1
        for d in p.delete:
            out.delete.append(d)
            out.delete_chunk[d] = cid
        if p.status == "unclear":
            out.unclear.append((cid, p.why))
        if p.status == "all_live":
            c = _cosines(members)
            if float(c[np.triu_indices(len(members), 1)].min()) >= 0.9999:
                out.identical_live_pairs += 1
    return out


# --- the copy-instance side ---------------------------------------------------------------------
def http(path: str, body: dict | None = None, method: str = "POST", timeout: int = 900):
    req = urllib.request.Request(  # noqa: S310 - fixed loopback http base, so no file: or custom scheme
        COPY + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=timeout))  # noqa: S310


def duplicated_chunks(collection: str) -> dict[str, list[int]]:
    seen: dict[str, list[int]] = collections.defaultdict(list)
    off = None
    while True:
        r = http(
            f"/collections/{collection}/points/scroll",
            {
                "limit": 5000,
                "offset": off,
                "with_payload": ["chunk_id"],
                "with_vector": False,
            },
        )["result"]
        for p in r["points"]:
            cid = (p.get("payload") or {}).get("chunk_id")
            if cid is not None:
                seen[cid].append(p["id"])
        off = r["next_page_offset"]
        if off is None:
            return {c: ids for c, ids in seen.items() if len(ids) > 1}


def load_members(
    collection: str, dup: dict[str, list[int]], direction: np.ndarray
) -> dict[str, list[Member]]:
    by_id = {i: c for c, ids in dup.items() for i in ids}
    ids = list(by_id)
    out: dict[str, list[Member]] = collections.defaultdict(list)
    for i in range(0, len(ids), 500):
        for p in http(
            f"/collections/{collection}/points",
            {"ids": ids[i : i + 500], "with_payload": False, "with_vector": ["dense"]},
        )["result"]:
            v = np.array(p["vector"]["dense"], dtype=np.float64)
            out[by_id[p["id"]]].append(Member(p["id"], v, detector_score(v, direction)))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("collection")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.collection in FORBIDDEN:
        sys.exit(
            f"REFUSED: {a.collection} is an original; this writes to the copy instance only."
        )
    names = {
        c["name"] for c in http("/collections", method="GET")["result"]["collections"]
    }
    if a.collection not in names:
        sys.exit(f"no collection {a.collection!r} on the copy instance")
    direction = np.load(DIRECTION).astype(np.float64)
    before = http(f"/collections/{a.collection}", method="GET")["result"][
        "points_count"
    ]
    dup = duplicated_chunks(a.collection)
    members = load_members(a.collection, dup, direction)
    pl = plan_collection(members)
    st = pl.statuses
    print(
        f"{a.collection}: {before:,} points; {len(dup):,} chunk ids on more than one point ({sum(len(v) for v in dup.values()):,} points)"
    )
    print(
        f"  dead copy with a live twin (to delete): {st['dead_removed']:,} groups, {len(pl.delete):,} points"
    )
    print(
        f"  every copy live (KEEP ALL, A126 amended): {st['all_live']:,} groups, of which {pl.identical_live_pairs:,} are the SAME vector"
    )
    print(
        f"  unclear (KEEP ALL): {st['unclear']:,}"
        + (f", first 3: {pl.unclear[:3]}" if pl.unclear else "")
    )
    if not a.apply:
        print("DRY RUN: nothing written. Re-run with --apply.")
        return
    if not pl.delete:
        print("nothing to delete")
        return
    BACKUP.mkdir(parents=True, exist_ok=True)
    backup = BACKUP / f"{a.collection}_deleted.jsonl"
    with backup.open("a") as f:
        for i in range(0, len(pl.delete), 200):
            for p in http(
                f"/collections/{a.collection}/points",
                {
                    "ids": pl.delete[i : i + 200],
                    "with_payload": True,
                    "with_vector": True,
                },
            )["result"]:
                f.write(json.dumps(p) + "\n")
    for i in range(0, len(pl.delete), 500):
        http(
            f"/collections/{a.collection}/points/delete?wait=true",
            {"points": pl.delete[i : i + 500]},
        )
    after = http(f"/collections/{a.collection}", method="GET")["result"]["points_count"]
    still = duplicated_chunks(a.collection)
    survive = http(f"/collections/{a.collection}/points/count", {"exact": True})[
        "result"
    ]["count"]
    lost = [
        c
        for c in {pl.delete_chunk[d] for d in pl.delete}
        if c not in still and not _has_chunk(a.collection, c)
    ]
    print(
        f"DELETED {len(pl.delete):,}: {before:,} -> {after:,} points (expected {before - len(pl.delete):,}); backup {backup}"
    )
    print(
        f"  chunk ids that lost their LAST copy: {len(lost)} (must be 0); count check {survive:,}"
    )
    sys.exit(0 if after == before - len(pl.delete) and not lost else 1)


def _has_chunk(collection: str, chunk_id: str) -> bool:
    r = http(
        f"/collections/{collection}/points/scroll",
        {
            "limit": 1,
            "filter": {"must": [{"key": "chunk_id", "match": {"value": chunk_id}}]},
            "with_payload": False,
            "with_vector": False,
        },
    )["result"]
    return bool(r["points"])


if __name__ == "__main__":
    main()
