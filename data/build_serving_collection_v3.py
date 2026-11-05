#!/usr/bin/env python3
"""MANIFEST for a new serving collection that takes the India Code supplement (A183). DRY RUN: it
writes a manifest and a list of record ids to remove, and nothing else. It never creates, writes
or deletes a Qdrant collection, never embeds, and never calls a vendor.

Plain words. The new collection (a name you pass with --collection, beside `kanoon_v1`) would be:

    kanoon_v1's points
      MINUS every point of the eight Acts the supplement replaces      (removed)
      PLUS  the supplement's chunks for those eight Acts and the Constitution    (added)
      EXCEPT supplement chunks that stay OFF                           (held)

One source per Act, never mixed: a replaced Act's `kanoon_v1` points are removed in full, so no
section can exist twice with different text. Stamp Schedule I (63 articles) and the Stamp state
blocks are held OFF (A183: the duty column is not reliably attached to its row). CrPC 1973, Consumer
Protection 1986 and Gratuity 1972 are not in the supplement at all (data/supplement_hold.py).

The guard is the one in data/sparse_fix.py: --collection is required with no default, the four
originals are refused in every mode, and so is the original Qdrant instance (port 6333). Because this
script only READS `kanoon_v1` (a scroll and a count, on the copy instance), the named target is used
only for the refusal check and the manifest header.

    .venv/bin/python data/build_serving_collection_v3.py --collection research_v3 \\
        --supplement-chunks <out>/supplement_chunks.jsonl --out-dir <dir>
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data.sparse_fix import check_target  # noqa: E402

SOURCE = "kanoon_v1"  # read only
# kanoon_v1 act_id -> supplement slug (one source per Act, never mixed)
REPLACES = {
    "IND_central_2187": "contract1872",
    "IND_central_2191": "cpc1908",
    "IND_central_1565": "limitation1963",
    "IND_central_15510": "stamp1899",
    "IND_central_2189": "nia1881",
    "IND_central_1560": "hma1955",
    "IND_central_1583": "sra1963",
    "IND_central_1558": "pca1988",  # conditional on A183 task 5: no newer wording found in kanoon_v1
}
ADDED_ONLY = ("constitution",)  # in the supplement, not in kanoon_v1
CONDITIONAL = {
    "pca1988": "PDF is as on 21 May 2025; task 5 found no newer wording in kanoon_v1"
}
SOURCE_KIND_DATASET = "dataset"
SOURCE_KIND_SUPPLEMENT = "supplement_indiacode"


def is_held(chunk: dict) -> str:
    """A reason this supplement chunk stays OFF, or ''."""
    if chunk["act_id"] == "IND_SUPP_stamp1899":
        if chunk.get("section_type") == "schedule_article":
            return "stamp Schedule I: duty column not reliably attached to its row"
        if chunk.get("state_amendment"):
            return "stamp state-amendment block: held until reviewed"
    return ""


def _post(url: str, body: dict) -> dict:
    req = urllib.request.Request(  # noqa: S310
        url, json.dumps(body).encode(), {"content-type": "application/json"}
    )
    return json.load(urllib.request.urlopen(req, timeout=120))["result"]  # noqa: S310


def kanoon_points(base: str, act_ids: list[str]) -> dict[str, list[str]]:
    """chunk_ids of `kanoon_v1` per Act id. READ ONLY: scroll with a filter."""
    out: dict[str, list[str]] = defaultdict(list)
    for aid in act_ids:
        off = None
        while True:
            body = {
                "limit": 1000,
                "with_vector": False,
                "with_payload": {"include": ["chunk_id"]},
                "filter": {"must": [{"key": "act_id", "match": {"value": aid}}]},
            }
            if off is not None:
                body["offset"] = off
            r = _post(f"{base}/collections/{SOURCE}/points/scroll", body)
            out[aid] += [p["payload"]["chunk_id"] for p in r["points"]]
            off = r["next_page_offset"]
            if off is None:
                break
    return out


def plan(
    total_kanoon: int,
    removed: dict[str, list[str]],
    chunks: list[dict],
    questions: list[dict],
) -> dict:
    """Pure function: everything in the manifest except the I/O. Easy to test."""
    removed_ids = {i for ids in removed.values() for i in ids}
    wanted = {f"IND_SUPP_{s}" for s in [*REPLACES.values(), *ADDED_ONLY]}
    added, held = [], []
    for c in chunks:
        if c["act_id"] not in wanted:
            continue
        why = is_held(c)
        (held if why else added).append((c, why))
    per_act: dict[str, dict] = {}
    for aid, slug in REPLACES.items():
        a = [c for c, _ in added if c["act_id"] == f"IND_SUPP_{slug}"]
        h = [c for c, _ in held if c["act_id"] == f"IND_SUPP_{slug}"]
        per_act[slug] = {
            "kanoon_act_id": aid,
            "removed_points": len(removed.get(aid, [])),
            "added_chunks": len(a),
            "held_off_chunks": len(h),
            "added_minus_removed": len(a) - len(removed.get(aid, [])),
            "added_not_checked": sum(
                1 for c in a if c["section_status"] == "not_checked"
            ),
            "added_repealed_or_omitted": sum(
                1 for c in a if c["section_status"] != "not_checked"
            ),
            "conditional": CONDITIONAL.get(slug, ""),
        }
    for slug in ADDED_ONLY:
        a = [c for c, _ in added if c["act_id"] == f"IND_SUPP_{slug}"]
        per_act[slug] = {
            "kanoon_act_id": None,
            "removed_points": 0,
            "added_chunks": len(a),
            "held_off_chunks": 0,
            "added_minus_removed": len(a),
            "added_not_checked": sum(
                1 for c in a if c["section_status"] == "not_checked"
            ),
            "added_repealed_or_omitted": sum(
                1 for c in a if c["section_status"] != "not_checked"
            ),
            "conditional": "",
        }
    kept = total_kanoon - len(removed_ids)
    ids = [c["chunk_id"] for c, _ in added]
    # gold-label check: any eval question whose expected / forbidden record is a removed id
    gold_hits = []
    for q in questions:
        refs = [
            *q.get("expect_records", []),
            *q.get("must_not_cite", []),
            *(q.get("also_accept") or []),
        ]
        bad = [r for r in refs if r in removed_ids]
        if bad:
            gold_hits.append(
                {"id": q["id"], "status": q.get("status"), "removed_ids": bad}
            )
    return {
        "kanoon_v1_points": total_kanoon,
        "kept": kept,
        "removed": len(removed_ids),
        "supplement_added": len(added),
        "supplement_held_off": len(held),
        "final_count": kept + len(added),
        "duplicate_ids_in_added": len(ids) - len(set(ids)),
        "added_ids_without_supp_prefix": sum(
            1 for i in ids if not i.startswith("IND_SUPP_")
        ),
        "source_kind": {SOURCE_KIND_DATASET: kept, SOURCE_KIND_SUPPLEMENT: len(added)},
        "held_off_reasons": dict(Counter(w for _, w in held)),
        "per_act": per_act,
        "eval_gold_labels_pointing_at_removed_ids": gold_hits,
        "eval_questions": len(questions),
        "eval_questions_with_any_gold_record": sum(
            1 for q in questions if q.get("expect_records") or q.get("must_not_cite")
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--collection", default=None, help="the NEW collection's name (required)"
    )
    ap.add_argument("--url", default="http://localhost:7333")
    ap.add_argument("--supplement-chunks", type=Path, required=True)
    ap.add_argument("--questions", type=Path, default=Path("evals/question_set.jsonl"))
    ap.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args(argv)
    target, base = check_target(a.collection, a.url)
    if target == SOURCE:
        sys.exit("ABORT: the target cannot be the source.")
    total = _post(f"{base}/collections/{SOURCE}/points/count", {"exact": True})["count"]
    removed = kanoon_points(base, list(REPLACES))
    chunks = [
        json.loads(ln)
        for ln in a.supplement_chunks.read_text(encoding="utf-8").splitlines()
    ]
    qs = [
        json.loads(ln)
        for ln in a.questions.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    m = plan(total, removed, chunks, qs)
    m.update(
        target_collection=target,
        source_collection=SOURCE,
        dry_run=True,
        wrote_to_qdrant=False,
    )
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / "serving_v3_manifest.json").write_text(
        json.dumps(m, indent=2), encoding="utf-8"
    )
    with (a.out_dir / "serving_v3_removed_record_ids.csv").open(
        "w", encoding="utf-8"
    ) as fh:
        fh.write("kanoon_act_id,chunk_id\n")
        for aid, ids in removed.items():
            for i in ids:
                fh.write(f"{aid},{i}\n")
    print(
        json.dumps(
            {
                k: m[k]
                for k in (
                    "kanoon_v1_points",
                    "kept",
                    "removed",
                    "supplement_added",
                    "supplement_held_off",
                    "final_count",
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
