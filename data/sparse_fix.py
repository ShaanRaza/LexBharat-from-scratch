#!/usr/bin/env python3
"""Repair the sparse (BM25) vectors on Central Act points in acts_india.

Only points with payload jurisdiction == "central" whose stored sparse vector does NOT
match FastEmbed Qdrant/bm25 (document side, embed()) are touched. Only the named vector
"sparse" is written; the dense vector and the payload are never sent.

Modes
  plan     read-only. Scans Central points, reports how many would change. Writes nothing.
  apply    needs --confirm. Step 1: write ORIGINAL sparse vectors of every failing point
           to the backup file and verify it. Step 2: re-encode and update those points.
  restore  puts the ORIGINAL sparse vectors from the backup file back, then verifies.

GUARD (A137 area, owner decision under CLAUDE.md section 8, 4 Nov 2026): --collection is REQUIRED and
there is no default. Every collection the owner lists as an original (PROTECTED below) is refused
in every mode, `plan` included, and so is the original instance (port 6333). The script used to default to
`acts_india` on 6333 and would have written to it when run with no arguments. --url defaults to the copy
instance (7333).

Run with the isolated interpreter that has fastembed installed (COPY = the name of a copy):
  fe_venv/bin/python -I sparse_fix.py plan    --collection COPY
  fe_venv/bin/python -I sparse_fix.py apply   --collection COPY --backup DIR/central_sparse_backup.jsonl --confirm --limit 20   # rehearsal
  fe_venv/bin/python -I sparse_fix.py apply   --collection COPY --backup DIR/central_sparse_backup.jsonl --confirm --resume    # the rest
  fe_venv/bin/python -I sparse_fix.py restore --collection COPY --backup DIR/central_sparse_backup.jsonl --confirm
"""

import argparse
import json
import os
import sys
import time
import urllib.request

Q = "http://localhost:7333"  # the COPY instance; set from --url in main()
COLL = None  # set from --collection in main(); there is deliberately no default
# The originals, read-only (owner's list, 4 Nov 2026; the rule is in DATA-GAPS section 17, not spelled
# out in CLAUDE.md section 6). Refused in every mode.
PROTECTED = frozenset({"legal_corpus_v1", "legal_corpus_v2", "acts_india", "kanoon_v1"})
ORIGINAL_PORT = 6333  # the instance that holds the originals
FILTER = {"must": [{"key": "jurisdiction", "match": {"value": "central"}}]}
SCROLL_BATCH = 256
WRITE_BATCH = 128


def check_target(collection, url):
    """Return (collection, url) if it may be touched, else raise SystemExit with the reason."""
    if not collection:
        sys.exit(
            "ABORT: --collection is required (no default). Name a COPY, never an original."
        )
    if collection in PROTECTED:
        sys.exit(
            f"ABORT: {collection!r} is an original named in CLAUDE.md section 6 (read-only). "
            "Run this against a copy."
        )
    if url.rstrip("/").rsplit(":", 1)[-1] == str(ORIGINAL_PORT):
        sys.exit(
            f"ABORT: {url} is the instance that holds the originals. Use the copy instance."
        )
    return collection, url.rstrip("/")


def call(method, path, body=None, retries=3):
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(  # noqa: S310 (fixed localhost URL)
                Q + path,
                data=data,
                method=method,
                headers={"Content-Type": "application/json"},
            )
            return json.load(urllib.request.urlopen(req, timeout=600))  # noqa: S310 (fixed localhost URL)
        except Exception as exc:  # noqa: BLE001
            if attempt == retries - 1:
                sys.exit(
                    f"ABORT: Qdrant call failed after {retries} tries: {method} {path}: {exc}"
                )
            time.sleep(3 * (attempt + 1))


def scan_central():
    """Yield (id, text, stored_sparse_dict) for every Central point."""
    offset = None
    while True:
        body = {
            "filter": FILTER,
            "limit": SCROLL_BATCH,
            "with_payload": ["text", "jurisdiction"],
            "with_vector": ["sparse"],
        }
        if offset is not None:
            body["offset"] = offset
        res = call("POST", f"/collections/{COLL}/points/scroll", body)["result"]
        for p in res["points"]:
            yield (
                p["id"],
                (p["payload"].get("text") or ""),
                p["vector"]["sparse"],
                p["payload"],
            )
        offset = res.get("next_page_offset")
        if offset is None:
            return


def encoder():
    from fastembed import SparseTextEmbedding

    return SparseTextEmbedding(model_name="Qdrant/bm25")


def encode(enc, text):
    e = next(enc.embed([text]))  # document side: embed(), NOT query_embed()
    return {
        "indices": e.indices.tolist(),
        "values": [float(v) for v in e.values.tolist()],
    }


def find_failing(enc):
    failing, total = [], 0
    for pid, text, stored, payload in scan_central():
        total += 1
        if payload.get("jurisdiction") != "central":
            sys.exit(
                f"ABORT: point {pid} came back with jurisdiction={payload.get('jurisdiction')!r}"
            )
        if not text:
            continue  # cannot re-encode an empty text; leave untouched
        if set(stored["indices"]) != set(encode(enc, text)["indices"]):
            failing.append((pid, text, stored))
        if total % 5000 == 0:
            print(f"  scanned {total:,}  failing so far {len(failing):,}", flush=True)
    return total, failing


def read_backup(path):
    out = {}
    with open(path) as fh:
        for line in fh:
            rec = json.loads(line)
            out[rec["id"]] = rec["sparse"]
    return out


def put_sparse(batch):
    pts = [{"id": pid, "vector": {"sparse": sp}} for pid, sp in batch]
    r = call("PUT", f"/collections/{COLL}/points/vectors?wait=true", {"points": pts})
    if r.get("status") != "ok":
        sys.exit(f"ABORT: update did not return ok: {r}")


def fetch_vectors(ids):
    res = call(
        "POST",
        f"/collections/{COLL}/points",
        {"ids": ids, "with_payload": False, "with_vector": ["dense", "sparse"]},
    )["result"]
    return {p["id"]: p["vector"] for p in res}


def cmd_plan(_):
    enc = encoder()
    total, failing = find_failing(enc)
    print(f"\nCentral points scanned : {total:,}")
    print(
        f"Would change (sparse)  : {len(failing):,}  ({100 * len(failing) / max(total, 1):.1f}%)"
    )
    print("Nothing was written.")


def cmd_apply(a):
    if not a.confirm:
        sys.exit("Refusing to write without --confirm.")
    if not a.backup:
        sys.exit("--backup PATH is required.")
    enc = encoder()
    existing = read_backup(a.backup) if os.path.exists(a.backup) else {}
    if existing and not a.resume:
        sys.exit(
            f"Backup {a.backup} already exists. Use --resume to continue; it is never overwritten."
        )
    total, failing = find_failing(enc)
    if a.limit:
        failing = failing[: a.limit]  # rehearsal: touch only the first N failing points
    todo = [f for f in failing if f[0] not in existing]
    print(
        f"Central scanned {total:,} | failing {len(failing):,} | not yet backed up {len(todo):,}"
    )

    # STEP 1: back up originals, fsync, then verify the file before touching Qdrant.
    with open(a.backup, "a") as fh:
        for pid, _text, stored in todo:
            fh.write(json.dumps({"id": pid, "sparse": stored}) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    saved = read_backup(a.backup)
    missing = [pid for pid, _t, _s in failing if pid not in saved]
    if missing:
        sys.exit(
            f"ABORT: backup is missing {len(missing)} points. Nothing was changed in Qdrant."
        )
    print(f"Backup verified: {len(saved):,} original sparse vectors in {a.backup}")

    # STEP 2: update only the sparse vector; prove dense is untouched on the first batch.
    done, first = 0, True
    for i in range(0, len(failing), WRITE_BATCH):
        chunk = failing[i : i + WRITE_BATCH]
        ids = [pid for pid, _t, _s in chunk]
        before = fetch_vectors(ids) if first else None
        new = [(pid, encode(enc, text)) for pid, text, _s in chunk]
        put_sparse(new)
        after = fetch_vectors(ids)
        for pid, sp in new:  # read-back: sparse must now match the encoder exactly
            if set(after[pid]["sparse"]["indices"]) != set(sp["indices"]):
                sys.exit(
                    f"ABORT: read-back mismatch on {pid}. Use restore with {a.backup}."
                )
        if first:
            for pid in ids:
                if before[pid]["dense"] != after[pid]["dense"]:
                    sys.exit(
                        f"ABORT: dense vector changed on {pid}. Use restore with {a.backup}."
                    )
            print(
                "Check passed: dense vectors identical before and after the first batch."
            )
            first = False
        done += len(chunk)
        if done % (WRITE_BATCH * 20) == 0 or done == len(failing):
            print(f"  updated {done:,}/{len(failing):,}", flush=True)
    print(f"\nDone. Updated {done:,} points. Originals kept in {a.backup}")


def cmd_restore(a):
    if not a.confirm:
        sys.exit("Refusing to write without --confirm.")
    saved = read_backup(a.backup)
    items = list(saved.items())
    for i in range(0, len(items), WRITE_BATCH):
        chunk = items[i : i + WRITE_BATCH]
        put_sparse(chunk)
        got = fetch_vectors([pid for pid, _ in chunk])
        for pid, sp in chunk:
            if (
                got[pid]["sparse"]["indices"] != sp["indices"]
                or got[pid]["sparse"]["values"] != sp["values"]
            ):
                sys.exit(f"ABORT: restored vector for {pid} does not equal the backup.")
    print(f"Restored and verified {len(items):,} original sparse vectors.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["plan", "apply", "restore"])
    ap.add_argument(
        "--collection", help="REQUIRED: the name of a copy (originals are refused)"
    )
    ap.add_argument("--url", default=Q, help="Qdrant URL (default: the copy instance)")
    ap.add_argument("--backup")
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument(
        "--limit", type=int, help="apply: change only the first N failing points"
    )
    a = ap.parse_args()
    COLL, Q = check_target(a.collection, a.url)
    {"plan": cmd_plan, "apply": cmd_apply, "restore": cmd_restore}[a.mode](a)
