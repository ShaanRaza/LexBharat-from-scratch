"""What loading the missing cases costs without an embedding API (A141 cost picture). Pipeline step 5 (Search) data
preparation measurement; nothing here changes behaviour and no Voyage call is made.

It takes a cluster sample of REAL chunks from the whole-missing English set (the same set DATA-GAPS section 19 counted;
courts that hold about 95% of it), then measures on this laptop:
  1. BM25 encoding speed (`fastembed`, the call the repo already uses for documents), one process and several;
  2. upsert speed and the disk a point takes, into two scratch collections on the COPY instance (127.0.0.1:7333)
     built exactly like `kanoon_v1` (int8 dense on disk, sparse with IDF, payload on disk):
       a141_disk_sparse_only    the points carry a BM25 vector and the payload, no dense vector
       a141_disk_dense_sparse   the same plus a 1,024-float dense vector (RANDOM values: disk size does not depend on
                                the values, but index build time might, so the dense timing is indicative only)
The payload is built from the parquet columns the served payload carries (text, ids, court, dates, parties, pages).

  .venv/bin/python -m evals.a141.load_cost --n 24000
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path

import numpy as np

from evals.a136.paths import DATA
from scan import coverage_gap as g
from scan import missing_set as ms

COPY = "http://127.0.0.1:7333"
STORAGE = Path.home() / "qdrant-kanoon" / "storage" / "collections"
SCRATCH = ("a141_disk_sparse_only", "a141_disk_dense_sparse")
COLS = [
    "case_id", "chunk_id", "chunk_index", "total_chunks", "text", "char_start", "char_end",
    "page_start", "page_end", "section_type", "year", "court", "court_code", "court_type",
    "bench_strength", "judges", "title", "petitioner", "respondent", "disposition",
    "case_number", "citation", "decision_date", "source_url", "language_code",
]  # fmt: skip


def call(method: str, path: str, body: dict | None = None) -> dict:
    """The copy instance only, and only the two scratch collections are ever written."""
    if method != "GET" and not any(
        path.startswith(f"/collections/{c}") for c in SCRATCH
    ):
        raise SystemExit(f"refused: {method} {path}")
    req = urllib.request.Request(  # noqa: S310 - fixed loopback http base
        COPY + path,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=300).read())["result"]  # noqa: S310


def sample_rows(home: Path, n: int, seed: int) -> list[dict]:
    """Cluster sample: random row groups of the big files, every whole-missing English row in them."""
    import pyarrow.parquet as pq

    results = json.loads((home / "results.json").read_text())
    codes = json.loads((home / "parquet" / "codes.json").read_text())
    en = json.loads((home / "parquet" / "langs.json").read_text())["en"]
    q_ch, q_ca = ms.load_q(home)
    weight = {c: v["whole_missing_english_chunks"] for c, v in results["codes"].items()}
    total_w = sum(weight.values())
    rng = np.random.default_rng(seed)
    out: list[dict] = []
    for f in sorted(g.PARQUET_DIR.glob("in_*_judgments.parquet")):
        z = np.load(home / "parquet" / (f.stem + ".npz"))
        ch, ca, co, lg = z["chash"], z["cash"], z["code"], z["lang"]
        share = sum(weight.get(codes[k], 0) for k in np.unique(co)) / total_w
        want = int(round(n * share))
        if want < 50:
            continue
        cand = np.flatnonzero(~np.isin(ch, q_ch) & (lg == en) & ~np.isin(ca, q_ca))
        pf = pq.ParquetFile(f)
        starts = np.cumsum(
            [0]
            + [
                pf.metadata.row_group(i).num_rows
                for i in range(pf.metadata.num_row_groups)
            ]
        )
        grp = np.searchsorted(starts, cand, side="right") - 1
        got = 0
        for rg in rng.permutation(np.unique(grp)):
            if got >= want:
                break
            rows = cand[grp == rg] - starts[rg]
            t = pf.read_row_group(int(rg), columns=COLS).take(rows.tolist())
            for r in t.to_pylist():
                out.append(r)
            got += len(rows)
        print(f"{f.name}: wanted {want:,}, took {got:,}", flush=True)
    return out


def to_payload(r: dict) -> dict:
    p = {k: r[k] for k in COLS if k != "source_url"}
    p.update(doc_id=r["case_id"], pdf_url=r["source_url"], country_code="IN")
    return p


def make_collection(name: str) -> None:
    cfg = call("GET", "/collections/kanoon_v1")["config"]["params"]
    call(
        "PUT",
        f"/collections/{name}",
        {
            "vectors": cfg["vectors"],
            "sparse_vectors": cfg["sparse_vectors"],
            "on_disk_payload": True,
        },
    )


def load(name: str, pts: list[dict]) -> float:
    t0 = time.time()
    for i in range(0, len(pts), 128):
        call(
            "PUT", f"/collections/{name}/points?wait=true", {"points": pts[i : i + 128]}
        )
    return time.time() - t0


def settle(name: str, limit_s: int = 1800) -> float:
    t0 = time.time()
    while time.time() - t0 < limit_s:
        info = call("GET", f"/collections/{name}")
        if info["status"] == "green" and str(info.get("optimizer_status")) == "ok":
            return time.time() - t0
        time.sleep(5)
    raise SystemExit(f"{name} did not settle in {limit_s}s")


def du_kb(path: Path) -> int:
    """Disk actually allocated under `path` (blocks, like `du`), in KiB."""
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            total += os.lstat(os.path.join(root, f)).st_blocks * 512
    return total // 1024


def main() -> None:
    from fastembed import SparseTextEmbedding

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=24000)
    ap.add_argument("--seed", type=int, default=41120)
    ap.add_argument("--home", default=str(g.HOME_DEFAULT))
    a = ap.parse_args()
    t0 = time.time()
    rows = sample_rows(Path(a.home), a.n, a.seed)
    texts = [r["text"] for r in rows]
    mean_chars = float(np.mean([len(t) for t in texts]))
    print(
        f"sample: {len(rows):,} chunks, mean {mean_chars:,.0f} chars ({time.time() - t0:.0f}s)",
        flush=True,
    )

    enc = SparseTextEmbedding(model_name="Qdrant/bm25")
    list(enc.embed(texts[:64]))  # model load and warm-up, not timed
    s0 = time.time()
    sparse = []
    for i in range(0, len(texts), 256):
        sparse += [
            (e.indices.tolist(), e.values.tolist())
            for e in enc.embed(texts[i : i + 256])
        ]
    single_s = time.time() - s0
    sub = texts[: min(8000, len(texts))]
    p0 = time.time()
    n_par = sum(1 for _ in enc.embed(sub, batch_size=256, parallel=0))  # 0 = all cores
    par_s = time.time() - p0
    enc_res = {
        "chunks": len(texts),
        "single_process_chunks_per_s": len(texts) / single_s,
        "parallel_all_cores_chunks_per_s": n_par / par_s,
        "parallel_sample": n_par,
        "cores": os.cpu_count(),
    }
    print("encode:", enc_res, flush=True)

    rng = np.random.default_rng(7)
    res: dict = {
        "sample_chunks": len(rows),
        "mean_chars": mean_chars,
        "encode": enc_res,
        "collections": {},
    }
    for name in SCRATCH:
        if name in [c["name"] for c in call("GET", "/collections")["collections"]]:
            raise SystemExit(f"{name} already exists; refusing to mix runs")
        make_collection(name)
        pts = []
        for r, (idx, val) in zip(rows, sparse):
            vec: dict = {"sparse": {"indices": idx, "values": val}}
            if name.endswith("dense_sparse"):
                d = rng.standard_normal(1024).astype(np.float32)
                vec["dense"] = (d / np.linalg.norm(d)).tolist()
            pts.append(
                {"id": g.H(r["chunk_id"]), "vector": vec, "payload": to_payload(r)}
            )
        up_s = load(name, pts)
        settle_s = settle(name)
        base = STORAGE / name
        kb = du_kb(base)
        parts = {
            c.name: du_kb(c)
            for c in base.rglob("*")
            if c.is_dir()
            and c.parent.name in ("0", name)
            and c.name in ("segments", "wal")
        }
        n = call("POST", f"/collections/{name}/points/count", {"exact": True})["count"]
        res["collections"][name] = {
            "points": n,
            "upsert_s": up_s,
            "upsert_points_per_s": len(pts) / up_s,
            "settle_s": settle_s,
            "disk_kb_total": kb,
            "disk_kb_by_part": parts,
            "bytes_per_point_total": kb * 1024 / n,
            "bytes_per_point_segments": parts.get("segments", 0) * 1024 / n,
        }
        print(name, res["collections"][name], flush=True)
    (DATA / "a141_load_cost.json").write_text(json.dumps(res, indent=1))
    print(f"done ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
