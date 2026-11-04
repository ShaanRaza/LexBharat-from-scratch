"""Per-court embedding health check (DECISIONS A141/A143; DATA-GAPS sections 13, 16, 19). Pipeline step 5 (Search)
measurement: nothing here changes behaviour and nothing here writes to any collection.

Plain words: before the owner approves the A141 backfill, find out whether any court besides Kerala holds vectors that
do not belong to their text, so a re-embed of those and the backfill can go into ONE batch. One job, every court, one
report. Three failure modes, tested separately:

  1. MISSING        the parquet has the chunk, Qdrant does not. Carried from section 19 (results.json / missing_set.json),
                    never re-measured.
  2. DEAD VECTORS   the stored dense vector scores below 0.10 against the legal-text direction (the existing detector,
                    data/dead_vectors/score_dense_vectors.py). Free. Reported by chunk-length band, because a long healthy
                    chunk scores lower (about 1% of them fall under the line, section 13).
  3. WRONG VECTOR   a random sample of each court's chunks is re-embedded with voyage-4 (input_type "document") and the
                    new vector is compared with the stored one. The stored vectors are NOT all voyage-4 (section 13: 73% of
                    a 2,640-chunk sample were voyage-4-lite or -large), so "near 1.0" is only one of three outcomes:
                      cosine >= 0.99        the stored vector is voyage-4's
                      0.50 to 0.99          the stored vector belongs to this text but another voyage-4-family model made it
                                            (identified chunks sit at 0.672 to 0.972: 41,692 in this run, 2,640 earlier)
                      below 0.50            the stored vector is unrelated to this text: dead, misaligned, or wrong text
                    0.50 is the line the Kerala re-embed used (A123); the 217,766 dead Kerala vectors re-embed at -0.138 to
                    +0.133 and the lowest other-model chunk is 0.672 (all 23 of this run's chunks below the earlier 0.839 were identified as lite or large by re-embedding), so nothing observed sits near the line.
                    Chunks between the highest dead vector and the lowest other-model chunk (0.14 to 0.67) would be reported separately as the unexplained middle; there are none.

Sampling is READ-ONLY on the originals (one request at a time, 0.25 s pause, a 60 s hard stop with no retry; resumable) and
draws about 60,000 points over the 49 (collection, court-prefix) groups. The group sizes are exact (from the saved section 19
scan); the court is the id prefix, not the `court` label (CLAUDE.md section 6).

Stages (each resumable; the output folder is outside the repo because it holds judgment text):
  plan      group sizes from the saved scan and the per-group sample sizes              -> plan.json
  sample    read-only draw from the originals                                           -> sample/<group>.jsonl + .npy
  price     exact Voyage tokens of the sample, counted locally; refuses above the cap   -> price.json
  embed     voyage-4 document embeddings (needs --go; hard cap; every request ledgered) -> embed/<group>.npy
  report    the table                                                                   -> report.json, REPORT.md

  python -m scan.embedding_health plan
  python -m scan.embedding_health sample
  python -m scan.embedding_health price
  python -m scan.embedding_health embed --go
  python -m scan.embedding_health report
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import math
import os
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

HOME = Path.home() / "qdrant-kanoon" / "embedding_health"
CG = Path.home() / "qdrant-kanoon" / "coverage_gap"
LEDGER = Path.home() / "qdrant-kanoon" / "kerala_fix" / "token_ledger.jsonl"
ORIG = "http://localhost:6333"
COLLECTIONS = ("legal_corpus_v1", "legal_corpus_v2")
# Reading is the only thing this script does to the originals; a path outside this list is refused before a request is made.
_READ_PATHS = re.compile(
    r"^/collections/(legal_corpus_v1|legal_corpus_v2)/points(/scroll|/count)?$"
)
HARD_STOP_S = 60
PAUSE_S = 0.25
FIELDS = [
    "chunk_id",
    "case_id",
    "court",
    "char_start",
    "char_end",
    "chunk_index",
    "text",
]

# sample sizes: a group is read whole when it is smaller than its quota
QUOTA_SMALL = 1100
QUOTA_BIG = 1800  # groups of a million points or more
BIG_FROM = 1_000_000
NOLABEL_QUOTA = 1000  # points with no `court` label, per collection
PAGE = (
    40  # points per random-offset read; consecutive ids are different cases (measured)
)
CENSUS_BELOW = 4000  # a label stratum this small is read whole
SEED = 20261104

# the three outcomes of the re-embed (see the module docstring for why these lines)
SAME = 0.99
UNRELATED_BELOW = 0.50
OTHER_MODEL_MIN_OBSERVED = 0.672  # the lowest identified lite/large chunk: 23 chunks first read as 'middle' at 0.672-0.837, all identified by re-embedding (middle_identify.json); the 2,640-chunk sample's lowest was 0.839
DEAD_MAX_OBSERVED = (
    0.133  # the highest of the 217,766 dead Kerala vectors re-embedded, A123
)
DETECTOR_LINE = 0.10
LENGTH_BANDS = [(0, 500), (500, 1500), (1500, 3000), (3000, 10**9)]

MODEL = "voyage-4"
PRICE_PER_MTOK = 0.06
BATCH_DISCOUNT = 0.33
CAP_USD = 6.00
CAP_TOKENS = int(CAP_USD / PRICE_PER_MTOK * 1e6)
EMBED_CALL = 50  # texts per request
WORKERS = 6
TAG = "health"


# ----------------------------------------------------------------------------------------------------------------------
# pure helpers (tested without any data)
# ----------------------------------------------------------------------------------------------------------------------
def classify(cos: np.ndarray) -> np.ndarray:
    """0 = voyage-4 reproduces the stored vector, 1 = another model of the family, 2 = unrelated to the text,
    3 = the unexplained middle (below any identified other-model chunk, above any dead one)."""
    c = np.asarray(cos, dtype=np.float64)
    out = np.full(c.shape, 1, dtype=np.int8)
    out[c >= SAME] = 0
    out[c < OTHER_MODEL_MIN_OBSERVED] = 3
    out[c < UNRELATED_BELOW] = 2
    return out


def cosine_rows(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    return (a * b).sum(1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval for a proportion; (0, 1) when n is 0."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def length_band(length: int) -> int:
    for i, (lo, hi) in enumerate(LENGTH_BANDS):
        if lo <= length < hi:
            return i
    return len(LENGTH_BANDS) - 1


def allocate(sizes: dict[tuple[str, str], int]) -> dict[tuple[str, str], int]:
    """Sample size per (collection, court code): QUOTA_SMALL, QUOTA_BIG for a million points or more, the whole group
    when it is smaller than its quota."""
    return {
        g: min(n, QUOTA_BIG if n >= BIG_FROM else QUOTA_SMALL) for g, n in sizes.items()
    }


def group_name(coll: str, code: str) -> str:
    return f"{coll[-2:]}_{code}"


def code_of(chunk_id: str) -> str:
    from scan import coverage_gap as g

    return g.code_of(chunk_id)


def price_usd(tokens: int, batch: bool = False) -> float:
    return tokens / 1e6 * PRICE_PER_MTOK * ((1 - BATCH_DISCOUNT) if batch else 1.0)


# ----------------------------------------------------------------------------------------------------------------------
# the originals: read-only
# ----------------------------------------------------------------------------------------------------------------------
READS = {"n": 0, "slowest": 0.0}


def orig_read(path: str, body: dict) -> dict:
    """One read of the ORIGINAL. A path that is not a read is refused; a failure or a request over HARD_STOP_S stops the
    run (no retry); a pause after every request."""
    if not _READ_PATHS.match(path):
        raise PermissionError(f"not a read of an original: {path}")
    req = urllib.request.Request(  # noqa: S310 - a fixed loopback http base, so no file: or custom scheme
        ORIG + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        raw = urllib.request.urlopen(req, timeout=HARD_STOP_S).read()  # noqa: S310
    except Exception as exc:  # noqa: BLE001
        sys.exit(
            f"HARD STOP reading the original: {exc}. No retry. State kept; re-run resumes."
        )
    dt = time.time() - t0
    READS["n"] += 1
    READS["slowest"] = max(READS["slowest"], dt)
    time.sleep(PAUSE_S)
    return json.loads(raw)["result"]


# ----------------------------------------------------------------------------------------------------------------------
# plan
# ----------------------------------------------------------------------------------------------------------------------
def crosstab() -> dict:
    """Points per (collection, id-prefix, label) from the saved section 19 scan pages. No Qdrant call."""
    out = {}
    codes = json.loads((CG / "parquet" / "codes.json").read_text())
    for coll in COLLECTIONS:
        labels = json.loads((CG / "scan" / coll / "labels.json").read_text())
        names = {v: k for k, v in labels.items()}
        cnt: collections.Counter = collections.Counter()
        for f in sorted((CG / "scan" / coll).glob("page_*.npz")):
            z = np.load(f)
            key = z["code"].astype(np.int64) * 100000 + z["label"]
            u, c = np.unique(key, return_counts=True)
            for a, b in zip(u.tolist(), c.tolist()):
                cnt[a] += b
        for k, v in cnt.items():
            ci, li = divmod(k, 100000)
            out.setdefault(coll, {}).setdefault(codes[ci], {})[names.get(li, "?")] = v
    return out


def build_plan() -> dict:
    ct = crosstab()
    sizes = {
        (coll, code): sum(labs.values())
        for coll, by in ct.items()
        for code, labs in by.items()
        if code != "?"
    }
    quotas = allocate(sizes)
    # a "stratum" is the set of groups read through one label filter. The main label of a group is its most common one.
    strata: dict[tuple[str, str], dict] = {}
    for (coll, code), n in sizes.items():
        labs = ct[coll][code]
        main = max((k for k in labs if k), key=lambda k: labs[k])
        s = strata.setdefault((coll, main), {"coll": coll, "label": main, "codes": {}})
        s["codes"][code] = {
            "points": n,
            "quota": quotas[(coll, code)],
            "frame": labs[main] / n,
        }
    for s in strata.values():
        total_label = sum(
            ct[s["coll"]][c].get(s["label"], 0) for c in ct[s["coll"]] if c != "?"
        )
        shares = [
            ct[s["coll"]][c].get(s["label"], 0) / max(total_label, 1)
            for c in s["codes"]
        ]
        s["label_points"] = total_label
        if total_label <= CENSUS_BELOW:
            s["mode"] = "census"
        elif len(s["codes"]) > 1 and min(shares) < 0.05:
            s["mode"] = "enumerate"
        else:
            s["mode"] = "runs"
    nolabel = {
        coll: {
            "points": sum(ct[coll][c].get("", 0) for c in ct[coll] if c != "?"),
            "quota": NOLABEL_QUOTA,
        }
        for coll in COLLECTIONS
    }
    plan = {
        "seed": SEED,
        "groups": {
            group_name(c, k): {
                "coll": c,
                "code": k,
                "points": n,
                "quota": quotas[(c, k)],
            }
            for (c, k), n in sorted(sizes.items())
        },
        "strata": [
            {
                **s,
                "key": f"{s['coll'][-2:]}__{re.sub('[^A-Za-z0-9]+', '_', s['label'])}",
            }
            for s in strata.values()
        ],
        "nolabel": nolabel,
        "sample_total": sum(quotas.values())
        + sum(v["quota"] for v in nolabel.values()),
        "points_total": sum(sizes.values()) + 0,
    }
    return plan


# ----------------------------------------------------------------------------------------------------------------------
# sample
# ----------------------------------------------------------------------------------------------------------------------
def _flt_label(label: str | None) -> dict:
    if label is None:
        return {"must": [{"is_empty": {"key": "court"}}]}
    return {"must": [{"key": "court", "match": {"value": label}}]}


def _row(p: dict, coll: str, run: int) -> dict:
    pl = p["payload"]
    return {
        "coll": coll,
        "id": p["id"],
        "chunk_id": pl.get("chunk_id"),
        "case_id": pl.get("case_id"),
        "label": pl.get("court") or "",
        "char_start": pl.get("char_start"),
        "char_end": pl.get("char_end"),
        "chunk_index": pl.get("chunk_index"),
        "text": pl.get("text") or "",
        "run": run,
    }


def _scroll_pages(coll, label, offset, limit, with_payload, with_vector):
    body = {
        "limit": limit,
        "filter": _flt_label(label),
        "with_payload": with_payload,
        "with_vector": with_vector,
    }
    if offset is not None:
        body["offset"] = offset
    return orig_read(f"/collections/{coll}/points/scroll", body)


def _enumerate_ids(coll: str, label: str | None) -> list[tuple[int, str]]:
    """(point id, chunk_id) of every point carrying the label; payload only, 5,000 per request."""
    out, off = [], None
    while True:
        res = _scroll_pages(coll, label, off, 5000, ["chunk_id"], False)
        out += [(p["id"], p["payload"].get("chunk_id") or "") for p in res["points"]]
        off = res.get("next_page_offset")
        if off is None:
            return out


def _retrieve(coll: str, ids: list[int]) -> list[dict]:
    out = []
    for i in range(0, len(ids), 100):
        res = orig_read(
            f"/collections/{coll}/points",
            {"ids": ids[i : i + 100], "with_payload": FIELDS, "with_vector": ["dense"]},
        )
        out += res
    return out


def _draw_runs(coll, label, quotas: dict[str, int], rnd: random.Random):
    """Random-offset runs of PAGE points over the label's points, offsets spread evenly over the id space (a shuffled
    jittered grid, repeated), until every code's quota is met. Consecutive ids are different cases, so a run is not a
    cluster of one case; the run index is kept anyway."""
    got = {c: [] for c in quotas}
    seen: set = set()
    run = 0
    cells = 64
    guard = 0
    while any(len(got[c]) < quotas[c] for c in quotas):
        order = list(range(cells))
        rnd.shuffle(order)
        for cell in order:
            off = int((cell + rnd.random()) / cells * (1 << 63))
            res = _scroll_pages(coll, label, off, PAGE, FIELDS, ["dense"])
            run += 1
            for p in res["points"]:
                code = code_of(p["payload"].get("chunk_id") or "")
                if (
                    code in got
                    and len(got[code]) < quotas[code]
                    and p["id"] not in seen
                ):
                    seen.add(p["id"])
                    got[code].append((p, run))
            if all(len(got[c]) >= quotas[c] for c in quotas):
                break
        guard += 1
        if guard > 400:
            print(
                f"  WARNING: {coll} {label!r}: stopped short of the quota", flush=True
            )
            break
    return got


def _write_group(
    name: str, coll: str, rows_vecs: list[tuple[dict, list[float], int]], frame: dict
) -> None:
    d = HOME / "sample"
    d.mkdir(parents=True, exist_ok=True)
    with (d / f"{name}.jsonl").open("w") as f:
        f.write(json.dumps({"_meta": frame}) + "\n")
        for p, _v, run in rows_vecs:
            f.write(json.dumps(_row(p, coll, run)) + "\n")
    np.save(
        d / f"{name}.npy",
        np.array([v for _p, v, _r in rows_vecs], dtype=np.float32).reshape(-1, 1024),
    )
    (d / f"{name}.done").write_text("1")


def _srs(items: list, k: int, rnd: random.Random) -> list:
    return list(items) if len(items) <= k else rnd.sample(items, k)


def cmd_sample(plan: dict) -> None:
    rnd = random.Random(plan["seed"])  # noqa: S311 (sampling, not security)
    d = HOME / "sample"
    d.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for s in plan["strata"]:
        names = {c: group_name(s["coll"], c) for c in s["codes"]}
        if all((d / f"{n}.done").exists() for n in names.values()):
            continue
        quotas = {c: v["quota"] for c, v in s["codes"].items()}
        print(f"{s['coll']} {s['label']!r} mode={s['mode']} codes={quotas}", flush=True)
        got: dict[str, list] = {}
        if s["mode"] == "runs":
            got = _draw_runs(s["coll"], s["label"], quotas, rnd)
        else:
            if s["mode"] == "census":
                pts, off = [], None
                while True:
                    res = _scroll_pages(
                        s["coll"], s["label"], off, 250, FIELDS, ["dense"]
                    )
                    pts += res["points"]
                    off = res.get("next_page_offset")
                    if off is None:
                        break
                by_code: dict[str, list] = {c: [] for c in quotas}
                for p in pts:
                    c = code_of(p["payload"].get("chunk_id") or "")
                    if c in by_code:
                        by_code[c].append((p, 0))
                got = {c: _srs(v, quotas[c], rnd) for c, v in by_code.items()}
            else:  # enumerate: every id with its chunk_id, simple random sample per code, then read those points
                ids = _enumerate_ids(s["coll"], s["label"])
                by_code = {c: [] for c in quotas}
                for pid, cid in ids:
                    c = code_of(cid)
                    if c in by_code:
                        by_code[c].append(pid)
                got = {}
                for c, v in by_code.items():
                    pts = _retrieve(s["coll"], _srs(v, quotas[c], rnd))
                    got[c] = [(p, 0) for p in pts]
        for c, lst in got.items():
            frame = {
                **s["codes"][c],
                "coll": s["coll"],
                "code": c,
                "label": s["label"],
                "mode": s["mode"],
                "n": len(lst),
            }
            _write_group(
                names[c],
                s["coll"],
                [(p, p["vector"]["dense"], r) for p, r in lst],
                frame,
            )
            print(
                f"  {names[c]}: {len(lst)} of {s['codes'][c]['points']:,} points  ({(time.time() - t0) / 60:.1f} min, {READS['n']} reads, slowest {READS['slowest']:.1f}s)",
                flush=True,
            )
    # the points with no court label: assigned to a court by id afterwards
    for coll, nl in plan["nolabel"].items():
        name = f"{coll[-2:]}_NOLABEL"
        if (d / f"{name}.done").exists():
            continue
        print(f"{coll} no court label: {nl['points']:,} points", flush=True)
        ids = _enumerate_ids(coll, None)
        pts = _retrieve(coll, _srs([pid for pid, _c in ids], nl["quota"], rnd))
        frame = {
            "coll": coll,
            "code": "NOLABEL",
            "label": "",
            "mode": "enumerate",
            "points": len(ids),
            "quota": nl["quota"],
            "n": len(pts),
        }
        _write_group(name, coll, [(p, p["vector"]["dense"], 0) for p in pts], frame)
        print(f"  {name}: {len(pts)} of {len(ids):,}", flush=True)
    print(
        f"SAMPLED. {READS['n']} reads of the originals, slowest {READS['slowest']:.1f}s, {(time.time() - t0) / 60:.1f} min"
    )


# ----------------------------------------------------------------------------------------------------------------------
# loading a sampled group
# ----------------------------------------------------------------------------------------------------------------------
def group_files() -> list[str]:
    return sorted(p.stem for p in (HOME / "sample").glob("*.done"))


def load_group(name: str):
    lines = (HOME / "sample" / f"{name}.jsonl").read_text().splitlines()
    frame = json.loads(lines[0])["_meta"]
    rows = [json.loads(x) for x in lines[1:]]
    vecs = np.load(HOME / "sample" / f"{name}.npy")
    if len(rows) != len(vecs):
        raise RuntimeError(f"{name}: {len(rows)} rows but {len(vecs)} vectors")
    return frame, rows, vecs


# ----------------------------------------------------------------------------------------------------------------------
# price (exact, local, free)
# ----------------------------------------------------------------------------------------------------------------------
def cmd_price() -> dict:
    from data import voyage_token_count as vtc

    per = {}
    total = 0
    for name in group_files():
        _f, rows, _v = load_group(name)
        arr = np.asarray(vtc.billed_tokens([r["text"] for r in rows]), dtype=np.int64)
        n_tok = int(arr.sum())
        per[name] = {"chunks": len(rows), "tokens": n_tok}
        np.save(HOME / "sample" / f"{name}.tokens.npy", arr)
        total += n_tok
    out = {
        "chunks": sum(v["chunks"] for v in per.values()),
        "tokens": total,
        "usd_standard": price_usd(total),
        "cap_usd": CAP_USD,
        "cap_tokens": CAP_TOKENS,
        "within_cap": total <= CAP_TOKENS,
        "per_group": per,
    }
    (HOME / "price.json").write_text(json.dumps(out, indent=1))
    print(
        f"{out['chunks']:,} chunks, {total:,} tokens (exact, local) = ${out['usd_standard']:.2f} at voyage-4 standard; cap ${CAP_USD:.2f} ({CAP_TOKENS:,} tokens): {'OK' if out['within_cap'] else 'OVER THE CAP, will not embed'}"
    )
    return out


# ----------------------------------------------------------------------------------------------------------------------
# embed
# ----------------------------------------------------------------------------------------------------------------------
def ledger_usd(prefix: str = TAG) -> float:
    """Dollars at list price for this job's ledger rows, each at its own model's price (the identification step used lite and
    large for a few tokens)."""
    from data.voyage_token_count import PRICE_PER_MTOK as prices

    if not LEDGER.exists():
        return 0.0
    usd = 0.0
    for line in LEDGER.open():
        r = json.loads(line)
        if str(r.get("tag", "")).startswith(prefix):
            usd += int(r["tokens"]) / 1e6 * prices[r["model"]]
    return usd


def ledger_tokens(prefix: str = TAG) -> int:
    if not LEDGER.exists():
        return 0
    n = 0
    for line in LEDGER.open():
        r = json.loads(line)
        if str(r.get("tag", "")).startswith(prefix):
            n += int(r["tokens"])
    return n


def _client(key: str):
    from pydantic import SecretStr

    from adapters.voyage import VoyageClient
    from core.settings import Settings

    s = Settings(_env_file=None)
    # a name for this job only; the model recorded for it is checked below, not defaulted
    s = s.model_copy(
        update={
            "VOYAGE_API_KEY": SecretStr(key),
            "VOYAGE_EMBED_MODELS": {"embedding_health": MODEL},
        }
    )
    if s.embed_model_for("embedding_health") != MODEL:
        raise RuntimeError("the job's model is not the one recorded for it")
    return VoyageClient(s, timeout_s=180, max_attempts=10)


def _ledger(tag: str, tokens: int) -> None:
    with LEDGER.open("a") as f:
        f.write(
            json.dumps({"t": time.time(), "model": MODEL, "tokens": tokens, "tag": tag})
            + "\n"
        )


async def _embed_group(
    client,
    name: str,
    texts: list[str],
    toks: np.ndarray,
    budget: dict,
    lock: asyncio.Lock,
    sem: asyncio.Semaphore,
):
    out: list = [None] * len(texts)

    async def one(i0: int):
        i1 = min(i0 + EMBED_CALL, len(texts))
        est = int(toks[i0:i1].sum())
        async with lock:
            if budget["used"] + budget["reserved"] + est > CAP_TOKENS:
                raise RuntimeError(
                    f"CAP: {budget['used']:,} used + {budget['reserved']:,} reserved + {est:,} next > {CAP_TOKENS:,}"
                )
            budget["reserved"] += est
        spent = 0
        try:
            async with sem:
                b = await client.embed_batch(
                    texts[i0:i1], "embedding_health", "document"
                )
            spent = b.total_tokens
            _ledger(f"{TAG}:{name}", spent)
            out[i0:i1] = b.vectors
        finally:
            async with lock:
                budget["reserved"] -= est
                budget["used"] += spent

    await asyncio.gather(*[one(i) for i in range(0, len(texts), EMBED_CALL)])
    return np.array(out, dtype=np.float32)


def _voyage_key() -> str:
    """The Voyage key from the environment or the repo .env; never printed."""
    key = os.environ.get("VOYAGE_API_KEY", "")
    if not key:
        envf = REPO / ".env"
        for line in envf.read_text().splitlines() if envf.exists() else []:
            if line.startswith("VOYAGE_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("\"'")
    if not key:
        sys.exit("REFUSED: no VOYAGE_API_KEY in the environment or the repo .env")
    return key


def cmd_embed(go: bool) -> None:
    if not go:
        sys.exit("REFUSED: embed spends money; it needs --go. Run `price` first.")
    price = (
        json.loads((HOME / "price.json").read_text())
        if (HOME / "price.json").exists()
        else None
    )
    if not price or not price["within_cap"]:
        sys.exit("REFUSED: no `price` result, or it is over the cap.")
    key = _voyage_key()
    client = _client(key)
    (HOME / "embed").mkdir(parents=True, exist_ok=True)
    pf = HOME / "preflight.json"
    if not pf.exists() or not json.loads(pf.read_text()).get("passed"):
        _preflight(client)
    budget = {"used": ledger_tokens(), "reserved": 0}
    start_used = budget["used"]
    print(
        f"tokens already on the ledger under '{TAG}': {start_used:,} of cap {CAP_TOKENS:,}",
        flush=True,
    )
    t0 = time.time()

    async def run():
        lock, sem = asyncio.Lock(), asyncio.Semaphore(WORKERS)
        for name in group_files():
            dest = HOME / "embed" / f"{name}.npy"
            if dest.exists():
                continue
            _f, rows, _v = load_group(name)
            toks = np.load(HOME / "sample" / f"{name}.tokens.npy")
            vecs = await _embed_group(
                client, name, [r["text"] for r in rows], toks, budget, lock, sem
            )
            np.save(dest, vecs)
            print(
                f"  {name}: {len(rows)} chunks  tokens this run {budget['used'] - start_used:,}  (${price_usd(budget['used'] - start_used):.3f})  {(time.time() - t0) / 60:.1f} min",
                flush=True,
            )

    try:
        asyncio.run(run())
    except RuntimeError as exc:
        if str(exc).startswith("CAP:"):
            print(f"STOPPED AT THE SPEND CAP: {exc}")
            sys.exit(3)
        raise
    print(
        f"EMBEDDED. tokens this run {budget['used'] - start_used:,} = ${price_usd(budget['used'] - start_used):.3f} at standard; cap ${CAP_USD:.2f}"
    )


def _preflight(client) -> None:
    """50 chunks of a group known to be voyage-4 (Bombay, collection 1: 114 of 114 identified chunks, section 13) must
    reproduce their stored vectors, or the method (document input_type, 1,024 dimensions, the text as stored) is wrong."""
    frame, rows, vecs = load_group("v1_HCBM")
    texts = [r["text"] for r in rows[:50]]
    b = asyncio.run(client.embed_batch(texts, "embedding_health", "document"))
    _ledger(f"{TAG}:preflight", b.total_tokens)
    cos = cosine_rows(np.array(b.vectors), vecs[:50])
    ok = bool((cos >= SAME).sum() >= 47 and np.median(cos) >= 0.999)
    pf = {
        "passed": ok,
        "n": 50,
        "median": float(np.median(cos)),
        "min": float(cos.min()),
        "n_at_least_0.99": int((cos >= SAME).sum()),
        "tokens": b.total_tokens,
    }
    (HOME / "preflight.json").write_text(json.dumps(pf))
    print(f"PREFLIGHT {'PASSED' if ok else 'FAILED'}: {pf}")
    if not ok:
        sys.exit("preflight failed: nothing more is embedded")


# ----------------------------------------------------------------------------------------------------------------------
# report
# ----------------------------------------------------------------------------------------------------------------------
def group_stats(name: str, direction: np.ndarray) -> dict:
    from data.dead_vectors.score_dense_vectors import score  # the existing detector

    frame, rows, vecs = load_group(name)
    new = np.load(HOME / "embed" / f"{name}.npy")
    toks = np.load(HOME / "sample" / f"{name}.tokens.npy")
    cos = cosine_rows(new, vecs)
    cls = classify(cos)
    det = score(vecs, direction)
    flagged = det < DETECTOR_LINE
    length = np.array([(r["char_end"] or 0) - (r["char_start"] or 0) for r in rows])
    band = np.array([length_band(int(x)) for x in length])
    codes = np.array([code_of(r["chunk_id"] or "") for r in rows])
    runs = np.array([r["run"] for r in rows])
    return {
        "frame": frame,
        "cos": cos,
        "cls": cls,
        "det": det,
        "flagged": flagged,
        "band": band,
        "tokens": toks,
        "codes": codes,
        "runs": runs,
        "chunk_ids": [r["chunk_id"] for r in rows],
    }


def cmd_report() -> None:
    from data.dead_vectors.score_dense_vectors import load_direction

    direction = load_direction()
    ids = json.loads((REPO / "core" / "court_ids.json").read_text())
    res = json.loads((CG / "results.json").read_text())["courts"]
    ms = json.loads((CG / "missing_set.json").read_text())["codes"]
    code_court = {c: slug for slug, ct in ids["courts"].items() for c in ct["prefixes"]}
    per_group = {}
    pooled = {"cos": [], "flagged": [], "band": [], "cls": []}
    for name in group_files():
        st = group_stats(name, direction)
        per_group[name] = st
        for k in ("cos", "flagged", "band", "cls"):
            pooled[k].append(st[k])
    pooled = {k: np.concatenate(v) for k, v in pooled.items()}
    # detector performance by length band, against the re-embed as truth (unrelated = cos below the line)
    truth = pooled["cls"] == 2
    det_by_band = []
    for b, (lo, hi) in enumerate(LENGTH_BANDS):
        m = pooled["band"] == b
        t, f = truth[m], pooled["flagged"][m]
        det_by_band.append(
            {
                "band": f"{lo}-{hi if hi < 10**8 else ''}",
                "n": int(m.sum()),
                "unrelated": int(t.sum()),
                "flagged": int(f.sum()),
                "flagged_and_unrelated": int((t & f).sum()),
                "flagged_but_related": int((~t & f).sum()),
                "unrelated_not_flagged": int((t & ~f).sum()),
            }
        )
    rows_out = []
    for name, st in per_group.items():
        fr = st["frame"]
        n = len(st["cos"])
        N = fr["points"]
        cls = st["cls"]
        k_unrel = int((cls == 2).sum())
        k_mid = int((cls == 3).sum())
        k_same = int((cls == 0).sum())
        k_other = int((cls == 1).sum())
        lo, hi = wilson(k_unrel, n)
        mean_tok = float(st["tokens"].mean())
        bands = []
        for b in range(len(LENGTH_BANDS)):
            m = st["band"] == b
            bands.append(
                {
                    "n": int(m.sum()),
                    "flagged": int(st["flagged"][m].sum()),
                    "unrelated": int((cls[m] == 2).sum()),
                }
            )
        rows_out.append(
            {
                "group": name,
                "coll": fr["coll"],
                "code": fr["code"],
                "points": N,
                "sampled": n,
                "census": n >= N,
                "same_model": k_same,
                "other_model": k_other,
                "unrelated": k_unrel,
                "middle": k_mid,
                "unrelated_rate": k_unrel / n,
                "unrelated_ci95": [lo, hi],
                "unrelated_est_points": round(k_unrel / n * N),
                "unrelated_upper_points": math.ceil(hi * N) if n < N else k_unrel,
                "flagged": int(st["flagged"].sum()),
                "flagged_and_unrelated": int((st["flagged"] & (cls == 2)).sum()),
                "unrelated_not_flagged": int((~st["flagged"] & (cls == 2)).sum()),
                "bands": bands,
                "tokens_per_chunk": mean_tok,
                "cos_min": float(st["cos"].min()),
                "cos_p1": float(np.percentile(st["cos"], 1)),
                "cos_median": float(np.median(st["cos"])),
                "other_model_cos_range": [
                    float(st["cos"][cls == 1].min()),
                    float(st["cos"][cls == 1].max()),
                ]
                if k_other
                else None,
                "runs_with_an_unrelated": len({int(r) for r in st["runs"][cls == 2]}),
                "unrelated_chunk_ids": [
                    c for c, k in zip(st["chunk_ids"], cls) if k == 2
                ][:20],
                "middle_chunk_ids": [c for c, k in zip(st["chunk_ids"], cls) if k == 3][
                    :20
                ],
                "frame_share_of_group": fr.get("frame"),
            }
        )
    out = {
        "thresholds": {
            "same": SAME,
            "unrelated_below": UNRELATED_BELOW,
            "other_model_min_observed": OTHER_MODEL_MIN_OBSERVED,
            "dead_max_observed": DEAD_MAX_OBSERVED,
            "detector_line": DETECTOR_LINE,
        },
        "detector_by_length_band": det_by_band,
        "groups": rows_out,
        "missing": {
            "per_court": {
                k: {
                    x: v[x]
                    for x in (
                        "parquet_chunks",
                        "parquet_only_chunks",
                        "whole_missing_cases",
                        "parquet_only_in_whole_missing_cases",
                    )
                }
                for k, v in res.items()
            },
            "per_prefix_english_whole_case_chunks": {
                c: {"cases": v["cases"], "chunks": v["chunks"]} for c, v in ms.items()
            },
            "code_court": code_court,
        },
        "pooled": {
            "n": int(len(pooled["cos"])),
            "classes": {str(i): int((pooled["cls"] == i).sum()) for i in range(4)},
        },
        "ledger_tokens_this_job": ledger_tokens(),
        "ledger_usd_this_job": ledger_usd(),
    }
    (HOME / "report.json").write_text(json.dumps(out, indent=1, default=float))
    labels = {slug: ct["label"] for slug, ct in ids["courts"].items()}
    (HOME / "REPORT.md").write_text(render_markdown(out, labels))
    print(
        f"wrote {HOME / 'report.json'} and REPORT.md  ({len(rows_out)} groups, {out['pooled']['n']:,} chunks)"
    )


# Groups whose unrelated vectors were already re-embedded and paid for, so they are shown but never counted into the new batch.
ALREADY_RE_EMBEDDED = {
    "v2_KLHC": "A123: re-embedded into kerala_v2_fix (about $16); every dead point has a live twin (A126)"
}
A141_BATCH_USD = 137.57  # docs/A141-COST-PICTURE.md: 3,422M tokens, voyage-4 at batch rates, the national court excluded (A141)


def render_markdown(out: dict, court_label: dict[str, str]) -> str:
    """The report as one table per court, then the per-collection detail. Plain numbers; every figure is from report.json."""
    g = out["groups"]
    by_code: dict[str, list[dict]] = collections.defaultdict(list)
    for r in g:
        by_code[r["code"]].append(r)
    miss = out["missing"]["per_prefix_english_whole_case_chunks"]
    L = []
    L.append("# Embedding health, per court\n")
    L.append(
        f"Sample: {out['pooled']['n']:,} points over {len(g)} (collection, court) groups, read from the originals and re-embedded with "
        f"{MODEL} as documents. Tokens on the ledger for this job: {out['ledger_tokens_this_job']:,} = ${out['ledger_usd_this_job']:.2f} at standard list price.\n"
    )
    L.append("## One row per court (both collections together)\n")
    L.append(
        "| Court | Prefix | Missing: chunks in whole missing cases (A141 set) | Points (v1+v2) | Sampled | Dead vectors, detector: flagged / long flagged | Re-embed: unrelated to text | Other voyage-4 model | Unexplained middle | Needs re-embedding: found, 95% upper bound (points) | At voyage-4 batch: found, upper bound |"
    )
    L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    tot = {"found": 0.0, "upper": 0.0, "found_usd": 0.0, "upper_usd": 0.0}
    for code in sorted(c for c in by_code if c != "NOLABEL"):
        rs = by_code[code]
        pts = sum(r["points"] for r in rs)
        n = sum(r["sampled"] for r in rs)
        fl = sum(r["flagged"] for r in rs)
        longn = sum(r["bands"][3]["n"] for r in rs)
        longf = sum(r["bands"][3]["flagged"] for r in rs)
        un = sum(r["unrelated"] for r in rs)
        oth = sum(r["other_model"] for r in rs)
        mid = sum(r["middle"] for r in rs)
        todo = [r for r in rs if r["group"] not in ALREADY_RE_EMBEDDED]
        found = sum(r["unrelated_est_points"] for r in todo)
        upper = sum(r["unrelated_upper_points"] for r in todo)
        per_mtok = PRICE_PER_MTOK * (1 - BATCH_DISCOUNT) / 1e6
        found_usd = (
            sum(r["unrelated_est_points"] * r["tokens_per_chunk"] for r in todo)
            * per_mtok
        )
        upper_usd = (
            sum(r["unrelated_upper_points"] * r["tokens_per_chunk"] for r in todo)
            * per_mtok
        )
        tot["found"] += found
        tot["upper"] += upper
        tot["found_usd"] += found_usd
        tot["upper_usd"] += upper_usd
        slug = out["missing"]["code_court"].get(code, "")
        name = court_label.get(slug, code)
        m = miss.get(code, {"chunks": 0})["chunks"]
        L.append(
            f"| {name} | {code} | {m:,} | {pts:,} | {n:,} | {fl} / {longf} of {longn:,} | **{un}** of {n:,} | {oth:,} | {mid} | **{found:,}**, up to {upper:,} | ${found_usd:,.2f}, up to ${upper_usd:,.2f} |"
        )
    courts = [r for r in g if r["code"] != "NOLABEL"]
    L.append(
        f"| **All courts** | | {sum(v['chunks'] for v in miss.values()):,} | {sum(r['points'] for r in courts):,} | {sum(r['sampled'] for r in courts):,} | | | | | **{tot['found']:,.0f}**, up to {tot['upper']:,.0f} | **${tot['found_usd']:,.2f}**, up to ${tot['upper_usd']:,.2f} |\n"
    )
    nl = [r for r in g if r["code"] == "NOLABEL"]
    if nl:
        L.append(
            f"Not a court: the points with no `court` label were sampled as their own stratum ({', '.join(f'{r["group"]}: {r["sampled"]:,} of {r["points"]:,}' for r in nl)}); their ids name a court, so they are already inside the court rows above. "
            f"Unrelated: {sum(r['unrelated'] for r in nl)}. Detector flagged: {sum(r['flagged'] for r in nl)}.\n"
        )
    for grp, why in ALREADY_RE_EMBEDDED.items():
        r = next((x for x in g if x["group"] == grp), None)
        if r:
            L.append(
                f"{grp} is shown but not counted: {r['unrelated']} of {r['sampled']:,} sampled are unrelated ({r['unrelated_rate']:.2%}), and it was already handled: {why}.\n"
            )
    L.append(
        f"Combined with A141's backfill (${A141_BATCH_USD:.2f} at batch): **${A141_BATCH_USD + tot['found_usd']:,.2f}** if only what was found is re-embedded, **${A141_BATCH_USD + tot['upper_usd']:,.2f}** at the 95% upper bound for every court.\n"
    )
    L.append(
        "## Per collection (a defect can sit in one collection of a court, as Kerala's did)\n"
    )
    L.append(
        "| Group | Points | Sampled | Whole group read | voyage-4's own | Other model | Unrelated | Middle | Unrelated rate (95% interval) | Detector flagged | Flagged and unrelated | Unrelated, not flagged | Tokens per chunk |"
    )
    L.append("|---|---:|---:|---|---:|---:|---:|---:|---|---:|---:|---:|---:|")
    for r in g:
        lo, hi = r["unrelated_ci95"]
        L.append(
            f"| {r['group']} | {r['points']:,} | {r['sampled']:,} | {'yes' if r['census'] else 'no'} | {r['same_model']:,} | {r['other_model']:,} | {r['unrelated']} | {r['middle']} | {r['unrelated_rate']:.2%} ({lo:.2%} to {hi:.2%}) | {r['flagged']} | {r['flagged_and_unrelated']} | {r['unrelated_not_flagged']} | {r['tokens_per_chunk']:,.0f} |"
        )
    L.append(
        "\n## The detector by chunk length, against the re-embed as truth (all groups pooled)\n"
    )
    L.append(
        "| Chunk length (characters) | Sampled | Unrelated by re-embed | Detector flagged | Flagged and unrelated | Flagged but related (false alarm) | Unrelated but not flagged (missed) |"
    )
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for b in out["detector_by_length_band"]:
        L.append(
            f"| {b['band']} | {b['n']:,} | {b['unrelated']:,} | {b['flagged']:,} | {b['flagged_and_unrelated']:,} | {b['flagged_but_related']:,} | {b['unrelated_not_flagged']:,} |"
        )
    t = out["thresholds"]
    L.append(
        f"\nLines: voyage-4's own at cosine >= {t['same']}; unrelated below {t['unrelated_below']}; the unexplained middle is below {t['other_model_min_observed']} and above {t['unrelated_below']} "
        f"(lowest identified other-model chunk {t['other_model_min_observed']}, highest dead Kerala vector {t['dead_max_observed']}). Detector line {t['detector_line']}."
    )
    return "\n".join(L) + "\n"


SPLIT_PER_GROUP = 100
SPLIT_CAP_USD = 0.80  # the split is about $0.6; refuse above this
SPLIT_SEED = 20261105


def split_plan() -> list[dict]:
    """Up to SPLIT_PER_GROUP off-model chunks per group (cosine to voyage-4 below 0.99
    and not unrelated), drawn at random. Pure reads of the saved sample."""
    rnd = random.Random(SPLIT_SEED)  # noqa: S311 (sampling, not security)
    out = []
    for name in group_files():
        if name.endswith("NOLABEL"):
            continue
        frame, rows, vecs = load_group(name)
        new = np.load(HOME / "embed" / f"{name}.npy")
        cls = classify(cosine_rows(new, vecs))
        off = [i for i in range(len(rows)) if cls[i] in (1, 3)]
        pick = sorted(rnd.sample(off, min(SPLIT_PER_GROUP, len(off))))
        out.append(
            {
                "group": name,
                "points": frame["points"],
                "off_model_in_sample": len(off),
                "healthy_in_sample": int(((cls == 0) | (cls == 1) | (cls == 3)).sum()),
                "pick": pick,
            }
        )
    return out


def cmd_split(go: bool) -> None:
    """Which model made each off-model chunk? Re-embed a sample under voyage-4-lite and
    voyage-4-large; a chunk whose stored vector reproduces (cosine 0.99 or more) under
    one of them was made by it. Sizes the share where model mismatch measurably costs
    recall (large chunks, A128)."""
    from data import voyage_token_count as vtc

    plan = split_plan()
    texts: list[str] = []
    stored: list = []
    owner: list[str] = []
    for g in plan:
        _f, rows, vecs = load_group(g["group"])
        for i in g["pick"]:
            texts.append(rows[i]["text"])
            stored.append(vecs[i])
            owner.append(g["group"])
    toks = int(sum(vtc.billed_tokens(texts)))
    usd = (
        toks
        / 1e6
        * (vtc.PRICE_PER_MTOK["voyage-4-lite"] + vtc.PRICE_PER_MTOK["voyage-4-large"])
    )
    print(
        f"{len(texts):,} chunks, {toks:,} tokens each under lite and large = ${usd:.2f} (exact, local); cap ${SPLIT_CAP_USD:.2f}",
        flush=True,
    )
    if usd > SPLIT_CAP_USD or ledger_usd() + usd > CAP_USD:
        sys.exit("REFUSED: over the cap")
    if not go:
        sys.exit("REFUSED: the split spends money; it needs --go")
    key = _voyage_key()
    from pydantic import SecretStr

    from adapters.voyage import VoyageClient
    from core.settings import Settings

    base = Settings(_env_file=None).model_copy(
        update={
            "VOYAGE_API_KEY": SecretStr(key),
            "VOYAGE_EMBED_MODELS": {
                "split_lite": "voyage-4-lite",
                "split_large": "voyage-4-large",
            },
        }
    )
    client = VoyageClient(base, timeout_s=180, max_attempts=10)
    sims: dict[str, np.ndarray] = {}
    for coll, model in (
        ("split_lite", "voyage-4-lite"),
        ("split_large", "voyage-4-large"),
    ):
        vecs_new = []
        for i in range(0, len(texts), EMBED_CALL):
            b = asyncio.run(
                client.embed_batch(texts[i : i + EMBED_CALL], coll, "document")
            )
            with LEDGER.open("a") as f:
                f.write(
                    json.dumps(
                        {
                            "t": time.time(),
                            "model": model,
                            "tokens": b.total_tokens,
                            "tag": f"{TAG}:split-{model}",
                        }
                    )
                    + "\n"
                )
            vecs_new += b.vectors
        sims[model] = cosine_rows(np.array(vecs_new), np.array(stored))
        print(f"  {model} done", flush=True)
    lite, large = sims["voyage-4-lite"], sims["voyage-4-large"]
    made = np.where(
        lite >= SAME, "lite", np.where(large >= SAME, "large", "unidentified")
    )
    res = []
    for g in plan:
        m = np.array(owner) == g["group"]
        n = int(m.sum())
        k = {x: int((made[m] == x).sum()) for x in ("lite", "large", "unidentified")}
        res.append(
            {**{k_: v for k_, v in g.items() if k_ != "pick"}, "sampled": n, **k}
        )
    (HOME / "split.json").write_text(
        json.dumps(
            {
                "per_group": res,
                "lite_min_cos_of_identified": float(lite[made == "lite"].min())
                if (made == "lite").any()
                else None,
                "large_min_cos_of_identified": float(large[made == "large"].min())
                if (made == "large").any()
                else None,
                "ledger_usd_this_job": ledger_usd(),
            },
            indent=1,
        )
    )
    tot = {x: int((made == x).sum()) for x in ("lite", "large", "unidentified")}
    print(f"SPLIT {tot}; job ledger now ${ledger_usd():.3f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "stage", choices=["plan", "sample", "price", "embed", "report", "split"]
    )
    ap.add_argument("--go", action="store_true", help="embed: spend (required)")
    a = ap.parse_args()
    HOME.mkdir(parents=True, exist_ok=True)
    if a.stage == "plan":
        p = build_plan()
        (HOME / "plan.json").write_text(json.dumps(p, indent=1))
        print(
            f"{len(p['groups'])} groups, {p['points_total']:,} points, sample {p['sample_total']:,}"
        )
        for s in p["strata"]:
            print(
                f"  {s['coll'][-2:]} {s['label']!r:42} {s['mode']:9} label points {s['label_points']:>10,}  codes { ({c: v['quota'] for c, v in s['codes'].items()}) }"
            )
    elif a.stage == "sample":
        cmd_sample(json.loads((HOME / "plan.json").read_text()))
    elif a.stage == "price":
        cmd_price()
    elif a.stage == "embed":
        cmd_embed(a.go)
    elif a.stage == "split":
        cmd_split(a.go)
    else:
        cmd_report()


if __name__ == "__main__":
    main()
