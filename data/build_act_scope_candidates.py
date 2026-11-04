#!/usr/bin/env python3
"""Candidate list of central-by-nature Acts stored under STATE record ids (A152/A153), for an
advocate to review. READ-ONLY: it scrolls one collection and writes two CSV files. It decides
nothing: `data/act_scope.json` (the reviewed table) does not exist until a person writes it.

Plain words: some central Acts (the Code of Criminal Procedure 1973, the Payment of Gratuity
Act 1972, ...) exist in the dataset only as copies published by state or UT websites, stored
under `IND_state_*` ids with `jurisdiction = state` and the publishing state's name. Three
independent signals flag a probable central Act under a state record:

  S1  the title equals a central Act's title in `kanoon_v1` (after normalising case, 'The',
      punctuation, '(No. x of y)'; titles with a '(Rep., ...)' suffix do NOT match, which is
      why S1 undercounts)
  S2  the same normalised title is republished by 3 or more states and has no state name in it
  S3  territorial extent says 'the whole of India' and the title has no state name in it

A signal is a hint, not a finding. S3 can catch a state Act that merely mentions its extent;
S2 can catch an Act that a few neighbouring states each adopted. Review per GROUP (one row per
normalised title), then per copy.

    .venv/bin/python data/build_act_scope_candidates.py --out-dir data/review
Writes act_scope_candidate_groups.csv (review this one) and act_scope_candidates.csv (every copy).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data.sparse_fix import check_target  # noqa: E402

FIELDS = [
    "act_id",
    "title",
    "jurisdiction",
    "state",
    "territorial_extent",
    "source_url",
    "chunk_index",
]
STATE_WORDS = (
    "andhra arunachal assam bihar chhattisgarh goa gujarat haryana himachal jharkhand karnataka "
    "kerala madhya maharashtra manipur meghalaya mizoram nagaland odisha orissa punjab rajasthan "
    "sikkim tamil telangana tripura uttar uttarakhand bengal delhi puducherry pondicherry "
    "chandigarh ladakh kashmir lakshadweep andaman nicobar dadra nagar daman diu bombay madras "
    "mysore travancore cochin hyderabad"
).split()


def norm(title: str | None) -> str:
    t = re.sub(r"^the\s+", "", (title or "").lower().strip())
    t = re.sub(r"\(\s*no\.?[^)]*\)|[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def names_a_state(title: str | None) -> bool:
    low = (title or "").lower()
    return any(re.search(rf"\b{w}\b", low) for w in STATE_WORDS)


def scroll(base: str, coll: str, flt: dict | None):
    off = None
    while True:
        body = {"limit": 2000, "with_payload": FIELDS, "with_vector": False}
        if flt:
            body["filter"] = flt
        if off is not None:
            body["offset"] = off
        req = urllib.request.Request(  # noqa: S310 (operator-supplied localhost URL)
            f"{base}/collections/{coll}/points/scroll",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        res = json.load(urllib.request.urlopen(req, timeout=600))["result"]  # noqa: S310
        yield from (p["payload"] for p in res["points"])
        off = res.get("next_page_offset")
        if off is None:
            return


def candidates(central_titles: set[str], acts: dict[str, dict]) -> dict[str, set[str]]:
    """act_id -> the signals that fired, for jurisdiction=state Acts only."""
    state_acts = {i: a for i, a in acts.items() if a["jurisdiction"] == "state"}
    states_by_title: dict[str, set] = defaultdict(set)
    for a in state_acts.values():
        states_by_title[norm(a["title"])].add(a["state"])
    out: dict[str, set[str]] = {}
    for i, a in state_acts.items():
        sig = set()
        if norm(a["title"]) in central_titles:
            sig.add("S1")
        if len(states_by_title[norm(a["title"])]) >= 3 and not names_a_state(
            a["title"]
        ):
            sig.add("S2")
        ext = (a.get("territorial_extent") or "").lower()
        if re.search(r"whole of india|all india", ext) and not names_a_state(
            a["title"]
        ):
            sig.add("S3")
        if sig:
            out[i] = sig
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--source", default="acts_noncentral_v1", help="staging collection (read only)"
    )
    ap.add_argument(
        "--central",
        default="kanoon_v1",
        help="collection holding the central Acts (read only)",
    )
    ap.add_argument("--url", default="http://localhost:7333")
    ap.add_argument("--out-dir", type=Path, default=Path("data/review"))
    a = ap.parse_args(argv)
    _, base = check_target(
        a.source + "_unused", a.url
    )  # only the URL check matters: never port 6333
    central = {
        norm(p["title"])
        for p in scroll(
            base,
            a.central,
            {"must": [{"key": "jurisdiction", "match": {"value": "central"}}]},
        )
    }
    acts: dict[str, dict] = {}
    for p in scroll(base, a.source, None):
        row = acts.setdefault(
            p["act_id"],
            {**{k: p.get(k) for k in FIELDS}, "points": 0, "first_text": ""},
        )
        row["points"] += 1
    hits = candidates(central, acts)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list[str]] = defaultdict(list)
    for i in hits:
        groups[norm(acts[i]["title"])].append(i)
    with open(a.out_dir / "act_scope_candidates.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "group",
                "act_id",
                "title",
                "hosting_state",
                "points",
                "signals",
                "source_url",
            ]
        )
        for g, ids in sorted(groups.items()):
            for i in sorted(ids):
                r = acts[i]
                w.writerow(
                    [
                        g,
                        i,
                        r["title"],
                        r["state"],
                        r["points"],
                        "+".join(sorted(hits[i])),
                        r["source_url"],
                    ]
                )
    with open(a.out_dir / "act_scope_candidate_groups.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "group",
                "example_title",
                "copies",
                "hosting_states",
                "points_per_copy",
                "signals_seen",
                "also_in_central_set",
                "proposed_canonical_act_id",
                "reviewer_verdict (central/state/unsure)",
                "repealed_by (if any)",
                "reviewer_note",
                "reviewed_by",
                "reviewed_on",
            ]
        )
        for g, ids in sorted(
            groups.items(), key=lambda kv: -sum(acts[i]["points"] for i in kv[1])
        ):
            sig = sorted({s for i in ids for s in hits[i]})
            best = max(ids, key=lambda i: (acts[i]["points"], i))
            w.writerow(
                [
                    g,
                    acts[ids[0]]["title"],
                    len(ids),
                    "; ".join(sorted({str(acts[i]["state"]) for i in ids})),
                    "/".join(str(x) for x in sorted({acts[i]["points"] for i in ids})),
                    "+".join(sig),
                    "yes" if g in central else "no",
                    best,
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )
    pts = sum(acts[i]["points"] for i in hits)
    print(
        f"{len(hits)} candidate act_ids in {len(groups)} title groups, {pts:,} points; wrote {a.out_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
