#!/usr/bin/env python3
"""Overnight lane A (team/overnight-A-coverage-gap.md): is law missing from the search index?

Plain words: Kerala turned up 117,119 chunks (111,804 whole cases) that are in the source parquet and in NO
Qdrant collection, so no search can ever find them. This checks every court. For each court it compares the
set of chunk ids in the parquet with the set in the original Qdrant collections (legal_corpus_v1 and v2
together) and separates WHOLE MISSING CASES (invisible law) from scattered missing chunks (a findable case
that is incomplete). It then spot-checks parquet-only cases to see whether they are real judgments or rows
deliberately left out (empty, placeholder, not English).

Stages, each resumable, run in order by `all` (a detached background job; the session may exit):

  parquet   read chunk_id / language_code of the 26 judgment files, hash them (no text)      -> parquet/<file>.npz
  scan      READ-ONLY scroll of legal_corpus_v2 then legal_corpus_v1 (chunk_id, court per point) -> scan/<coll>/page_*.npz
  analyze   per-court comparison, whole-case vs scattered, label rates, spot-check, §19 text   -> results.json, SECTION19.md
  commit    append §19 to docs/DATA-GAPS.md and commit it locally (that path only); never pushes

Guards: the originals are only READ (one request at a time, 0.25 s pause). Nothing is embedded, no Voyage call,
no cost. Request timeout 60 s; every page is checkpointed; on a failed or slow request it waits 30 s and retries
the same page, and after 5 CONSECUTIVE failures it hard-stops (state kept; re-running resumes). Abandoning a
checkpointed read-only scan is worse than retrying it (owner's instruction for the night of 3-4 Nov 2026; this
is not CLAUDE.md section 9's 60 s, which is about service starts).

    python scan/coverage_gap.py all          # the whole job
    python scan/coverage_gap.py status       # one line of progress
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
HOME_DEFAULT = Path.home() / "qdrant-kanoon" / "coverage_gap"
PARQUET_DIR = Path("/Volumes/LAWSSD/open-india-law")
ORIG = "http://localhost:6333"
COLLECTIONS = ["legal_corpus_v2", "legal_corpus_v1"]
PAGE = 5000
TIMEOUT_S = 60
PAUSE_S = 0.25
BACKOFF_S = 30
MAX_CONSECUTIVE_FAILURES = 5
# The one court name this script prints comes from core/coverage.json (A51); none is typed here.
_SC_NAME = next(
    c["name"]
    for c in json.loads((REPO / "core" / "coverage.json").read_text())["courts"]
    if c["id"] == "supreme_court"
)
LAUNCH_CODES = {
    "HCBM": "Bombay",
    "HBHC": "Telangana",
    "KLHC": "Kerala",
    "INSC": _SC_NAME,
}
# The gate binds on WHOLE MISSING CASES (owner, 4 Nov 2026): a case Qdrant holds no chunk of is invisible law, while
# scattered missing chunks leave a findable case incomplete. The threshold (1% of a court's English cases) is still my
# number, not the owner's. The scattered-chunk rate is reported beside it and does not bind.
GATE_THRESHOLD_PCT = 1.0
SPOT_N = 20


# --- small pure helpers (tested in tests/test_coverage_gap.py) ---------------------------------------------
def H(s: str) -> int:
    return int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8).digest(), "big")


def case_key(chunk_id: str) -> str:
    """The case a chunk belongs to: its id without the trailing _<n> (measured: chunk_id starts with its case_id)."""
    return chunk_id.rsplit("_", 1)[0]


_LETTERS = re.compile(r"[A-Za-z]+")
_SC = re.compile(r"^\d{4}_INSC_")


def code_of(chunk_id: str) -> str:
    """The id prefix naming the court (core/court_id.py), 'INSC' for the national court, '?' when unknown."""
    if _SC.match(chunk_id):
        return "INSC"
    m = _LETTERS.match(chunk_id)
    return m.group(0) if m else "?"


def compare(p_chash, p_cash, q_chash, q_cash) -> dict:
    """The core comparison for ONE court, on arrays of 64-bit hashes. Parquet and Qdrant chunk sets, and for the
    parquet-only chunks whether the case is wholly absent from Qdrant or partly present."""
    pu, idx = np.unique(p_chash, return_index=True)
    pcase = p_cash[idx]
    qu = np.unique(q_chash)
    in_q = np.isin(pu, qu)
    only_p = ~in_q
    qcases = np.unique(q_cash)
    whole = only_p & ~np.isin(pcase, qcases)
    partial = only_p & ~whole
    pcases_all = np.unique(pcase)
    q_only = ~np.isin(qu, pu)
    pcases_known = np.unique(p_cash)
    q_case_of = np.unique(q_cash)  # cases present in Qdrant
    q_only_cases_whole = len(np.setdiff1d(q_case_of, pcases_known))
    return {
        "parquet_chunks": int(len(pu)),
        "parquet_cases": int(len(pcases_all)),
        "qdrant_chunks": int(len(qu)),
        "overlap_chunks": int(in_q.sum()),
        "parquet_only_chunks": int(only_p.sum()),
        "parquet_only_in_whole_missing_cases": int(whole.sum()),
        "parquet_only_in_partial_cases": int(partial.sum()),
        "whole_missing_cases": int(len(np.unique(pcase[whole]))),
        "partial_cases": int(len(np.unique(pcase[partial]))),
        "qdrant_only_chunks": int(q_only.sum()),
        "qdrant_only_whole_cases": int(q_only_cases_whole),
        "_only_p_mask": only_p,
        "_whole_mask": whole,
        "_idx": idx,
    }


# --- the original, read only ------------------------------------------------------------------------------------
class Stop(Exception):
    pass


def orig_post(path: str, body: dict, log) -> dict:
    """One read of the original with the night's retry rule. Only scroll and count are allowed."""
    if not re.match(
        r"^/collections/(legal_corpus_v1|legal_corpus_v2)/points/(scroll|count)$", path
    ):
        raise Stop(f"refused non-whitelisted path {path}")
    fails = 0
    while True:
        t0 = time.time()
        try:
            req = urllib.request.Request(
                ORIG + path,
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
            )
            raw = urllib.request.urlopen(req, timeout=TIMEOUT_S).read()  # noqa: S310
            if time.time() - t0 > TIMEOUT_S:
                raise TimeoutError(f"took {time.time() - t0:.1f}s")
            time.sleep(PAUSE_S)
            return json.loads(raw)["result"]
        except Exception as exc:  # noqa: BLE001
            fails += 1
            log(
                f"FAIL {fails}/{MAX_CONSECUTIVE_FAILURES} on {path} after {time.time() - t0:.1f}s: {exc}"
            )
            if fails >= MAX_CONSECUTIVE_FAILURES:
                raise Stop(f"{fails} consecutive failures on {path}: {exc}") from exc
            time.sleep(BACKOFF_S)


class Ctx:
    def __init__(self, home: Path):
        self.home = home
        home.mkdir(parents=True, exist_ok=True)
        self.status_path = home / "status.json"
        self.progress = home / "progress.log"
        self.timeouts = 0

    def log(self, msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        with self.progress.open("a") as f:
            f.write(line + "\n")
        print(line, flush=True)
        if msg.startswith("FAIL"):
            self.timeouts += 1

    def status(self, **kw) -> None:
        cur = (
            json.loads(self.status_path.read_text())
            if self.status_path.exists()
            else {}
        )
        cur.update(
            kw,
            updated=time.strftime("%Y-%m-%d %H:%M:%S"),
            failures_logged=self.timeouts,
        )
        tmp = self.status_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(cur, indent=1))
        os.replace(tmp, self.status_path)


def court_table():
    raw = json.loads((REPO / "core" / "court_ids.json").read_text())
    codes = sorted(c for ct in raw["courts"].values() for c in ct["prefixes"])
    return raw, codes


# --- stage: parquet ----------------------------------------------------------------------------------------------
def stage_parquet(ctx: Ctx, limit_files: int | None = None) -> None:
    import pyarrow.parquet as pq

    raw, codes = court_table()
    codes = [*codes, "?"]
    cidx = {c: i for i, c in enumerate(codes)}
    out = ctx.home / "parquet"
    out.mkdir(exist_ok=True)
    langs: dict[str, int] = (
        json.loads((out / "langs.json").read_text())
        if (out / "langs.json").exists()
        else {}
    )
    files = sorted(PARQUET_DIR.glob("in_*_judgments.parquet"))[: limit_files or None]
    ctx.status(stage="parquet", parquet_files=len(files))
    for n, f in enumerate(files, 1):
        dst = out / (f.stem + ".npz")
        if dst.exists():
            continue
        t0 = time.time()
        ch, ca, co, lg = [], [], [], []
        for b in pq.ParquetFile(f).iter_batches(
            batch_size=200_000, columns=["chunk_id", "language_code"]
        ):
            ids = b.column(0).to_pylist()
            ls = b.column(1).to_pylist()
            for cid, lc in zip(ids, ls):
                ch.append(H(cid))
                ca.append(H(case_key(cid)))
                co.append(cidx.get(code_of(cid), cidx["?"]))
                lg.append(langs.setdefault((lc or "").lower(), len(langs)))
        np.savez(
            dst,
            chash=np.array(ch, dtype=np.uint64),
            cash=np.array(ca, dtype=np.uint64),
            code=np.array(co, dtype=np.int8),
            lang=np.array(lg, dtype=np.int16),
        )
        (out / "langs.json").write_text(json.dumps(langs))
        ctx.log(
            f"parquet {n}/{len(files)} {f.name}: {len(ch):,} rows in {time.time() - t0:.0f}s"
        )
        ctx.status(parquet_done=n)
    (out / "codes.json").write_text(json.dumps(codes))
    ctx.status(parquet_complete=True)


# --- stage: scan ----------------------------------------------------------------------------------------------------
def stage_scan(
    ctx: Ctx, collections: list[str], limit_pages: int | None = None
) -> None:
    _, codes = court_table()
    cidx = {c: i for i, c in enumerate([*codes, "?"])}
    for coll in collections:
        d = ctx.home / "scan" / coll
        d.mkdir(parents=True, exist_ok=True)
        sp = d / "state.json"
        st = (
            json.loads(sp.read_text())
            if sp.exists()
            else {"offset": None, "pages": 0, "points": 0, "done": False}
        )
        if st["done"]:
            ctx.log(f"{coll}: already scanned ({st['points']:,} points)")
            continue
        total = orig_post(
            f"/collections/{coll}/points/count", {"exact": True}, ctx.log
        )["count"]
        st["count_at_start"] = total
        lab_path = d / "labels.json"
        labels: dict[str, int] = (
            json.loads(lab_path.read_text()) if lab_path.exists() else {}
        )
        t0, p0, pages_this_run = time.time(), st["points"], 0
        ctx.status(stage="scan", collection=coll, total=total)
        while True:
            body = {
                "limit": PAGE,
                "with_payload": ["chunk_id", "court", "court_code"],
                "with_vector": False,
            }
            if st["offset"] is not None:
                body["offset"] = st["offset"]
            r = orig_post(f"/collections/{coll}/points/scroll", body, ctx.log)
            ch, ca, co, lb = [], [], [], []
            for p in r["points"]:
                pl = p["payload"]
                cid = pl.get("chunk_id") or ""
                ch.append(H(cid))
                ca.append(H(case_key(cid)))
                co.append(cidx.get(code_of(cid), cidx["?"]))
                lb.append(labels.setdefault(pl.get("court") or "", len(labels)))
            np.savez(
                d / f"page_{st['pages']:06d}.npz",
                chash=np.array(ch, dtype=np.uint64),
                cash=np.array(ca, dtype=np.uint64),
                code=np.array(co, dtype=np.int8),
                label=np.array(lb, dtype=np.int32),
            )
            lab_path.write_text(json.dumps(labels))
            st["pages"] += 1
            st["points"] += len(r["points"])
            st["offset"] = r.get("next_page_offset")
            st["done"] = st["offset"] is None
            sp.write_text(json.dumps(st))  # the checkpoint, every page
            pages_this_run += 1
            rate = (st["points"] - p0) / max(time.time() - t0, 1e-9)
            eta = (total - st["points"]) / max(rate, 1e-9) / 3600
            ctx.status(
                stage="scan",
                collection=coll,
                points=st["points"],
                total=total,
                pages=st["pages"],
                rate_pts_s=round(rate),
                eta_hours=round(eta, 2),
            )
            if st["pages"] % 20 == 0 or st["done"]:
                ctx.log(
                    f"{coll}: {st['points']:,}/{total:,} points ({st['points'] / total * 100:.1f}%), {rate:,.0f} pts/s, ETA {eta:.1f} h"
                )
            if st["done"] or (limit_pages and pages_this_run >= limit_pages):
                break
        if st["done"]:
            ctx.log(
                f"{coll}: SCAN COMPLETE {st['points']:,} points (collection count {total:,}) in {(time.time() - t0) / 60:.0f} min"
            )


def load_scan(ctx: Ctx, coll: str):
    d = ctx.home / "scan" / coll
    parts = [np.load(f) for f in sorted(d.glob("page_*.npz"))]

    def cat(k):
        if parts:
            return np.concatenate([p[k] for p in parts])
        return np.array([], dtype=np.uint64)

    return (
        cat("chash"),
        cat("cash"),
        cat("code"),
        cat("label"),
        json.loads((d / "labels.json").read_text()),
        json.loads((d / "state.json").read_text()),
    )


def load_parquet(ctx: Ctx):
    d = ctx.home / "parquet"
    parts = [np.load(f) for f in sorted(d.glob("in_*.npz"))]
    return (
        np.concatenate([p["chash"] for p in parts]),
        np.concatenate([p["cash"] for p in parts]),
        np.concatenate([p["code"] for p in parts]),
        np.concatenate([p["lang"] for p in parts]),
        json.loads((d / "langs.json").read_text()),
        json.loads((d / "codes.json").read_text()),
    )


# --- stage: analyze ---------------------------------------------------------------------------------------------------
def pct(a: int, b: int) -> float:
    return 100.0 * a / b if b else 0.0


def gate_row(c: dict) -> dict:
    """The gate figures of one court (or the total) from its roll-up counts. `whole_pct` BINDS: English cases that
    Qdrant holds no chunk of, as a share of the court's English cases. `scattered_pct` is reported beside it: English
    chunks missing from cases that are otherwise present, as a share of the court's English chunks."""
    return {
        "english_parquet_chunks": c["parquet_english_chunks"],
        "english_parquet_only": c["parquet_only_english_chunks"],
        "pct": pct(c["parquet_only_english_chunks"], c["parquet_english_chunks"]),
        "english_cases": c["parquet_english_cases"],
        "whole_missing_english_cases": c["whole_missing_english_cases"],
        "whole_missing_english_chunks": c["whole_missing_english_chunks"],
        "whole_pct": pct(c["whole_missing_english_cases"], c["parquet_english_cases"]),
        "scattered_english_chunks": c["partial_english_chunks"],
        "scattered_pct": pct(c["partial_english_chunks"], c["parquet_english_chunks"]),
    }


def gate_figures(codes: dict) -> dict:
    return {
        name: gate_row(codes[code])
        for code, name in LAUNCH_CODES.items()
        if codes.get(code)
    }


def verdict(gate: dict, overall: dict) -> dict:
    """The rule: a defect if whole missing English cases are GATE_THRESHOLD_PCT or more of the English cases of any
    launch court or overall. Says which condition tripped; the scattered-chunk rate is reported and never binds."""
    rows = {**gate, "All courts": overall}
    whole = [k for k, g in rows.items() if g["whole_pct"] >= GATE_THRESHOLD_PCT]
    scattered = [k for k, g in rows.items() if g["scattered_pct"] >= GATE_THRESHOLD_PCT]
    return {
        "tripped_whole_cases": whole,
        "scattered_would_trip": scattered,
        "verdict_defect": bool(whole),
    }


def stage_analyze(ctx: Ctx, partial_ok: bool = False) -> dict:
    raw, _ = court_table()
    P_ch, P_ca, P_co, P_lg, langs, codes = load_parquet(ctx)
    inv_lang = {v: k for k, v in langs.items()}
    scans = {c: load_scan(ctx, c) for c in COLLECTIONS}
    complete = {c: scans[c][5]["done"] for c in COLLECTIONS}
    if not all(complete.values()) and not partial_ok:
        raise Stop(f"a scan is not complete: {complete}")
    code_of_idx = {i: c for i, c in enumerate(codes)}
    en = langs.get("en")
    court_of_code = {
        code: cid for cid, c in raw["courts"].items() for code in c["prefixes"]
    }
    counts = {c: scans[c][5].get("count_at_start") for c in COLLECTIONS}
    res: dict = {
        "collection_counts": counts,
        "complete": complete,
        "scan_points": {c: int(len(scans[c][0])) for c in COLLECTIONS},
        "scan_state": {c: scans[c][5] for c in COLLECTIONS},
        "codes": {},
    }
    Q_ch = np.concatenate([scans[c][0] for c in COLLECTIONS])
    Q_ca = np.concatenate([scans[c][1] for c in COLLECTIONS])
    Q_co = np.concatenate([scans[c][2] for c in COLLECTIONS])
    ctx.status(stage="analyze")
    only_cases: dict[str, np.ndarray] = {}
    for ci, code in code_of_idx.items():
        pm, qm = P_co == ci, Q_co == ci
        if not pm.any() and not qm.any():
            continue
        cmp_ = compare(P_ch[pm], P_ca[pm], Q_ch[qm], Q_ca[qm])
        only_p, whole, idx = (
            cmp_.pop("_only_p_mask"),
            cmp_.pop("_whole_mask"),
            cmp_.pop("_idx"),
        )
        lang_u = P_lg[pm][idx]
        ca_u = P_ca[pm][idx]
        non_en = lang_u != en if en is not None else np.zeros_like(only_p)
        cmp_["parquet_english_chunks"] = int((~non_en).sum())
        cmp_["parquet_only_english_chunks"] = int((only_p & ~non_en).sum())
        cmp_["parquet_only_non_english_chunks"] = int((only_p & non_en).sum())
        cmp_["whole_missing_english_chunks"] = int((whole & ~non_en).sum())
        cmp_["partial_english_chunks"] = int((only_p & ~whole & ~non_en).sum())
        # a case is English if it has an English chunk
        cmp_["parquet_english_cases"] = int(len(np.unique(ca_u[~non_en])))
        cmp_["whole_missing_english_cases"] = int(len(np.unique(ca_u[whole & ~non_en])))
        cmp_["parquet_only_languages"] = dict(
            collections.Counter(inv_lang[int(x)] for x in lang_u[only_p]).most_common(6)
        )
        cmp_["overlap_pct"] = pct(cmp_["overlap_chunks"], cmp_["parquet_chunks"])
        cmp_["court"] = court_of_code.get(code, "?")
        res["codes"][code] = cmp_
        only_cases[code] = np.unique(
            ca_u[whole & ~non_en]
        )  # whole missing English cases, for the spot-check
    # court-level roll-up (a court may have several id prefixes)
    courts: dict[str, dict] = {}
    for code, c in res["codes"].items():
        k = c["court"]
        agg = courts.setdefault(k, collections.Counter())
        for f in (
            "parquet_chunks",
            "parquet_cases",
            "qdrant_chunks",
            "overlap_chunks",
            "parquet_only_chunks",
            "parquet_only_in_whole_missing_cases",
            "parquet_only_in_partial_cases",
            "whole_missing_cases",
            "partial_cases",
            "qdrant_only_chunks",
            "parquet_english_chunks",
            "parquet_only_english_chunks",
            "parquet_only_non_english_chunks",
            "whole_missing_english_chunks",
            "partial_english_chunks",
            "parquet_english_cases",
            "whole_missing_english_cases",
        ):
            agg[f] += c[f]
    res["courts"] = {k: dict(v) for k, v in courts.items()}
    tot = collections.Counter()
    for v in res["courts"].values():
        tot.update(v)
    res["total"] = dict(tot)
    # label rates across the whole originals (bonus: DATA-GAPS section 18's pending Qdrant-wide figure)
    lab = {}
    for coll in COLLECTIONS:
        ch, ca, co, lb, labels, _ = scans[coll]
        inv = {v: k for k, v in labels.items()}
        kinds = collections.Counter()
        pairs = collections.Counter(zip(co.tolist(), lb.tolist()))
        for (ci, li), n in pairs.items():
            code = code_of_idx[ci]
            if code == "?":
                kinds["id_names_no_court"] += n
                continue
            c = raw["courts"][court_of_code[code]]
            label = inv[li]
            same = {c["label"], *c["aliases"]}
            kinds[
                "usual"
                if label == c["label"]
                else "alias"
                if label in same
                else "missing"
                if not label
                else "other_court"
            ] += n
        lab[coll] = dict(kinds)
    res["labels"] = lab
    # launch-court gate figures and the verdict rule
    res["gate"] = gate_figures(res["codes"])
    t = res["total"]
    res["overall_english_pct"] = pct(
        t["parquet_only_english_chunks"], t["parquet_english_chunks"]
    )
    res["overall"] = gate_row(t)
    res.update(verdict(res["gate"], res["overall"]))
    # where the court came from (CLAUDE.md section 6: a court label is missing on 0.58% of rows, so a label-based
    # comparison would drop exactly the rows most likely to be absent)
    unk = codes.index("?")
    res["court_source"] = {
        "method": "chunk id prefix (core/court_ids.json) for the parquet AND for Qdrant; the payload `court` label is not used to assign a court",
        "parquet_rows_id_names_no_court": int((P_co == unk).sum()),
        "qdrant_points_id_names_no_court": {
            c: int((scans[c][2] == unk).sum()) for c in COLLECTIONS
        },
        "qdrant_points_without_court_label": {
            c: int((scans[c][3] == scans[c][4].get("", -1)).sum()) for c in COLLECTIONS
        },
        "parquet_label_read": False,
    }
    # spot-check
    rnd = random.Random(2026)
    picks: list[tuple[str, int]] = []
    for code in ("KLHC", "HCBM", "HBHC"):
        for h in rnd.sample(
            list(only_cases.get(code, [])), min(3, len(only_cases.get(code, [])))
        ):
            picks.append((code, int(h)))
    for h in rnd.sample(
        list(only_cases.get("INSC", [])), min(2, len(only_cases.get("INSC", [])))
    ):
        picks.append(("INSC", int(h)))
    pool = [
        (c, int(h))
        for c, arr in only_cases.items()
        if c not in LAUNCH_CODES
        for h in arr
    ]
    weights_total = len(pool)
    for c, h in rnd.sample(pool, min(SPOT_N - len(picks), weights_total)):
        picks.append((c, h))
    res["spot_check_picks"] = picks
    (ctx.home / "results.json").write_text(json.dumps(res, indent=1, default=int))
    ctx.log(
        f"analysis done: total parquet-only {t['parquet_only_chunks']:,} of {t['parquet_chunks']:,} parquet chunks; verdict_defect={res['verdict_defect']}"
    )
    return res


# --- stage: spot-check (reads the parquet text of ~20 whole-missing cases) --------------------------------------------------
def stage_spotcheck(ctx: Ctx, res: dict) -> list[dict]:
    import duckdb
    import pyarrow.parquet as pq

    raw, _ = court_table()
    picks = res["spot_check_picks"]
    src_of_code = {
        code: cid for cid, c in raw["courts"].items() for code in c["prefixes"]
    }
    by_src: dict[str, list[tuple[str, int]]] = collections.defaultdict(list)
    for code, h in picks:
        by_src[src_of_code[code]].append((code, h))
    out = []
    con = duckdb.connect()
    for src, items in by_src.items():
        f = PARQUET_DIR / f"in_{src}_judgments.parquet"
        want = {h for _, h in items}
        keys: dict[int, str] = {}
        for b in pq.ParquetFile(f).iter_batches(
            batch_size=500_000, columns=["chunk_id"]
        ):
            for cid in b.column(0).to_pylist():
                k = case_key(cid)
                h = H(k)
                if h in want and h not in keys:
                    keys[h] = k
            if len(keys) == len(want):
                break
        ctx.log(f"spot-check {src}: resolved {len(keys)}/{len(want)} case ids")
        for code, h in items:
            k = keys.get(h)
            if not k:
                continue
            rows = con.execute(
                f"select chunk_id, language_code, length(text), substr(text, 1, 260), source_url from read_parquet('{f}') where starts_with(chunk_id, ?) order by chunk_index",
                [k + "_"],
            ).fetchall()
            n_q = {}
            for coll in COLLECTIONS:
                n_q[coll] = orig_post(
                    f"/collections/{coll}/points/count",
                    {
                        "exact": True,
                        "filter": {"must": [{"key": "case_id", "match": {"value": k}}]},
                    },
                    ctx.log,
                )["count"]
            lens = sorted(r[2] for r in rows)
            langs = collections.Counter((r[1] or "").lower() for r in rows)
            med = lens[len(lens) // 2] if lens else 0
            low = (
                "non-English"
                if (langs and langs.most_common(1)[0][0] != "en")
                else "short or placeholder"
                if med < 300
                else "substantive English"
            )
            out.append(
                {
                    "code": code,
                    "case_id": k,
                    "chunks": len(rows),
                    "languages": dict(langs),
                    "median_chars": med,
                    "min_chars": lens[0] if lens else 0,
                    "short_chunks_lt200": sum(1 for x in lens if x < 200),
                    "class": low,
                    "in_qdrant_v1": n_q["legal_corpus_v1"],
                    "in_qdrant_v2": n_q["legal_corpus_v2"],
                    "source_url": rows[0][4] if rows else None,
                    "first_text": re.sub(r"\s+", " ", rows[0][3])[:200] if rows else "",
                }
            )
            ctx.log(
                f"spot-check {k}: {len(rows)} chunks, median {med} chars, {low}, in Qdrant v1/v2: {n_q['legal_corpus_v1']}/{n_q['legal_corpus_v2']}"
            )
    (ctx.home / "spotcheck.json").write_text(json.dumps(out, indent=1))
    return out


# --- stage: write-up -------------------------------------------------------------------------------------------------------
def write_section(ctx: Ctx, res: dict, spot: list[dict]) -> str:
    n = lambda x: f"{int(x):,}"  # noqa: E731
    t = res["total"]
    done = all(res["complete"].values())
    L = []
    L.append(
        "## 19. Is law missing from the search index? Per-court gap between the parquet and Qdrant\n"
    )
    L.append(
        f"**{time.strftime('%-d %b %Y')} (overnight lane A).** **{'Measured' if done else 'PARTIAL: a scan did not finish, figures are lower bounds on what Qdrant holds, so gaps are overstated'}**, "
        f"from an exhaustive read-only scroll of `legal_corpus_v2` ({n(res['scan_points']['legal_corpus_v2'])} points) and `legal_corpus_v1` ({n(res['scan_points']['legal_corpus_v1'])} points) "
        f"and all 26 judgment parquet files ({n(t['parquet_chunks'])} distinct chunk ids). A chunk counts as indexed if its id is in EITHER collection. Nothing was written to any Qdrant; no embedding, no cost. "
        f"The scan read {', '.join(f'{res["scan_points"][c]:,} points of {c} (its count was {res["collection_counts"][c]:,})' for c in COLLECTIONS)}. "
        f"The scan used the night's rule (60 s timeout, a checkpoint every page, 30 s back-off and retry, hard stop after 5 consecutive failures): {ctx.timeouts} failed or slow requests were logged and retried.\n"
    )
    L.append("### What was found\n")
    L.append(
        f"- **{n(t['parquet_only_chunks'])} of {n(t['parquet_chunks'])} parquet chunks ({pct(t['parquet_only_chunks'], t['parquet_chunks']):.2f}%) are in no Qdrant collection** (Measured). "
        f"**{n(t['parquet_only_in_whole_missing_cases'])} of them ({pct(t['parquet_only_in_whole_missing_cases'], t['parquet_only_chunks']):.0f}%) sit in {n(t['whole_missing_cases'])} WHOLE cases that Qdrant holds no chunk of at all** (invisible law); "
        f"{n(t['parquet_only_in_partial_cases'])} are scattered chunks of {n(t['partial_cases'])} cases that are otherwise present (findable but incomplete). "
        f"**{'Whole missing cases dominate.' if t['parquet_only_in_whole_missing_cases'] >= t['parquet_only_in_partial_cases'] else 'Scattered chunks dominate.'}**"
    )
    L.append(
        f"- Of the parquet-only chunks, {n(t['parquet_only_english_chunks'])} are English and {n(t['parquet_only_non_english_chunks'])} are not (the dataset card says English only; the non-English chunks of {_SC_NAME} are the known exclusion, section 8). "
        f"English parquet-only chunks are **{res['overall_english_pct']:.2f}%** of all English parquet chunks."
    )
    L.append(
        f"- The reverse: {n(t['qdrant_only_chunks'])} chunk ids are in Qdrant and not in the parquet.\n"
    )
    L.append("### Per court (all id prefixes of a court summed; Measured)\n")
    L.append(
        "| Court | Parquet chunks | In Qdrant | Overlap | Parquet-only | in whole missing cases | in partial cases | whole cases missing | English parquet-only | Qdrant-only |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    )
    for k, v in sorted(
        res["courts"].items(), key=lambda kv: -kv[1]["parquet_only_chunks"]
    ):
        L.append(
            f"| {k} | {n(v['parquet_chunks'])} | {n(v['overlap_chunks'])} | {pct(v['overlap_chunks'], v['parquet_chunks']):.1f}% | **{n(v['parquet_only_chunks'])}** | {n(v['parquet_only_in_whole_missing_cases'])} | {n(v['parquet_only_in_partial_cases'])} | {n(v['whole_missing_cases'])} | {n(v['parquet_only_english_chunks'])} | {n(v['qdrant_only_chunks'])} |"
        )
    L.append(
        f"| **Total** | {n(t['parquet_chunks'])} | {n(t['overlap_chunks'])} | {pct(t['overlap_chunks'], t['parquet_chunks']):.1f}% | **{n(t['parquet_only_chunks'])}** | {n(t['parquet_only_in_whole_missing_cases'])} | {n(t['parquet_only_in_partial_cases'])} | {n(t['whole_missing_cases'])} | {n(t['parquet_only_english_chunks'])} | {n(t['qdrant_only_chunks'])} |\n"
    )
    L.append("### The launch courts (CLAUDE.md section 1)\n")
    L.append(
        "The gate binds on the **whole-missing-case** column (a case Qdrant holds no chunk of at all is invisible law). The scattered-chunk column is the other shape (a findable case that is incomplete); it is reported beside it and does not bind.\n"
    )
    L.append(
        "| Court | English cases | **Whole English cases in no collection** | **Share of cases (binds)** | English chunks | English chunks scattered in present cases | Share of chunks (reported) | All English chunks in no collection |\n|---|---:|---:|---:|---:|---:|---:|---:|"
    )
    for name, g in [*res["gate"].items(), ("All courts", res["overall"])]:
        L.append(
            f"| {name} | {n(g['english_cases'])} | {n(g['whole_missing_english_cases'])} | **{g['whole_pct']:.2f}%** | {n(g['english_parquet_chunks'])} | {n(g['scattered_english_chunks'])} | {g['scattered_pct']:.2f}% | {n(g['english_parquet_only'])} ({g['pct']:.2f}%) |"
        )
    L.append("")
    L.append(
        f"### Spot-check: {len(spot)} wholly missing English cases read from the parquet (Measured; samples drawn at random, 3 each from Kerala, Bombay and Telangana, 2 {_SC_NAME}, the rest across other courts)\n"
    )
    cls = collections.Counter(s["class"] for s in spot)
    absent = sum(1 for s in spot if s["in_qdrant_v1"] == 0 and s["in_qdrant_v2"] == 0)
    L.append(
        f"Classes: {dict(cls)}. **Absence re-confirmed directly in Qdrant (an indexed `case_id` count on both collections): {absent} of {len(spot)} have 0 chunks.**\n"
    )
    if absent != len(spot):
        L.append(
            f"**WARNING: {len(spot) - absent} of the {len(spot)} spot-checked cases ARE present in Qdrant by a direct `case_id` count, so the hash comparison and the direct check DISAGREE for them. Treat the per-court table as suspect until this is explained (a case id that differs from the chunk-id prefix, or a scan that missed points).**\n"
        )
    L.append(
        "| Case id | Chunks | Languages | Median chars | Chunks under 200 chars | Class | Opens with |\n|---|---:|---|---:|---:|---|---|"
    )
    for s in spot:
        L.append(
            f"| `{s['case_id']}` | {s['chunks']} | {s['languages']} | {s['median_chars']} | {s['short_chunks_lt200']} | {s['class']} | {s['first_text'][:110].replace('|', '/')} |"
        )
    L.append("")
    L.append(
        "### Qdrant-wide `court` label rate (the figure section 18 left pending; Measured on the whole originals)\n"
    )
    for coll, k in res["labels"].items():
        tot = sum(k.values())
        L.append(
            f"- `{coll}`: {n(tot)} points: "
            + ", ".join(
                f"{name} {n(v)} ({pct(v, tot):.2f}%)"
                for name, v in sorted(k.items(), key=lambda kv: -kv[1])
            )
        )
    L.append("")
    cs = res["court_source"]
    L.append("### Where the court came from (CLAUDE.md section 6)\n")
    L.append(
        f"**The court of every row was taken from the chunk id, not from the `court` label**, on both sides: {cs['method']}. "
        f"A label-based comparison would silently drop the rows with no label, which are the rows most likely to be absent, and would understate the gap. "
        f"Ids that name no known court were kept, not dropped: {n(cs['parquet_rows_id_names_no_court'])} parquet rows and "
        + ", ".join(
            f"{n(v)} points of `{c}`"
            for c, v in cs["qdrant_points_id_names_no_court"].items()
        )
        + " (they are the `?` row of the court counts). "
        "Qdrant points with an empty `court` label (Measured; the rows a label-based comparison would have lost on the Qdrant side): "
        + ", ".join(
            f"`{c}` {n(v)}" for c, v in cs["qdrant_points_without_court_label"].items()
        )
        + ". The parquet `court` label was not read at all; the 0.58% missing-label rate for the parquet is section 6's figure, not re-measured here.\n"
    )
    L.append("### Verdict\n")
    rows = {**res["gate"], "All courts": res["overall"]}
    cases = "; ".join(
        f"{k} {g['whole_pct']:.2f}% ({n(g['whole_missing_english_cases'])} of {n(g['english_cases'])} cases)"
        for k, g in rows.items()
    )
    chunks = "; ".join(f"{k} {g['scattered_pct']:.2f}%" for k, g in rows.items())
    tw, ts = res["tripped_whole_cases"], res["scattered_would_trip"]
    L.append(
        f"By a rule that binds on whole missing cases (owner, 4 Nov 2026; the {GATE_THRESHOLD_PCT:.0f}% threshold is my number, not the owner's): **a defect for the launch gate if whole English cases absent from Qdrant are {GATE_THRESHOLD_PCT:.0f}% or more of a launch court's English cases, or of all English cases.** "
        f"Whole missing cases: {cases}. Scattered-chunk rate beside it (reported, does not bind): {chunks}.\n"
    )
    L.append(
        f"**Which condition tripped: whole missing cases {'TRIPPED in ' + ', '.join(tw) if tw else 'did not trip anywhere'}; the scattered-chunk rate {'would have tripped in ' + ', '.join(ts) if ts else 'did not reach the threshold anywhere'} (it does not bind).** "
        f"**{'This is a coverage DEFECT that belongs in the launch gate.' if res['verdict_defect'] else 'By that rule this is not a defect for the launch courts.'}** "
        f"The spot-check classes above say whether the missing cases are real judgments (substantive English) or rows left out on purpose; **read the table before trusting the rule: its classes are automatic (language and chunk length only) and were not read by a person.**\n"
    )
    L.append("### What this does not cover\n")
    L.append(
        "- Chunk presence is by id. A chunk present with the wrong text or an empty vector counts as present. Nothing here checks vectors.\n- The parquet is the reference: a chunk missing from the parquet but present in Qdrant is reported, not judged. The case key is the chunk id without its trailing `_<n>`, which matched the `case_id` in every parquet row measured earlier (section 18).\n- The overall `court` label counts treat an id that names no known court as unclassifiable. The classification of a missing case as real or placeholder is from language and length only for the ones not spot-checked.\n- The hashes are 64-bit (a collision among 64M ids has probability under 1e-4); not verified beyond that.\n"
    )
    text = "\n".join(L)
    (ctx.home / "SECTION19.md").write_text(text)
    return text


def stage_commit(ctx: Ctx, text: str) -> str:
    path = REPO / "docs" / "DATA-GAPS.md"
    dirty = (
        subprocess.run(
            ["git", "diff", "--quiet", "--", "docs/DATA-GAPS.md"], cwd=REPO
        ).returncode
        != 0
    )
    cur = path.read_text(encoding="utf-8")
    if "## 19. Is law missing from the search index?" in cur:
        return "section 19 already present; not appended"
    if dirty:
        return "docs/DATA-GAPS.md has uncommitted changes by someone else; section 19 left in SECTION19.md, not appended"
    path.write_text(cur.rstrip("\n") + "\n\n" + text + "\n", encoding="utf-8")
    for _ in range(5):
        subprocess.run(["git", "add", "docs/DATA-GAPS.md"], cwd=REPO)
        p = subprocess.run(
            [
                "git",
                "commit",
                "--only",
                "docs/DATA-GAPS.md",
                "-m",
                "docs: section 19 - per-court gap between the parquet and Qdrant (overnight lane A)\n\nPipeline steps touched: none (documentation, measured by a read-only scan).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        if p.returncode == 0:
            return "committed locally (not pushed)"
        time.sleep(10)
    return "commit failed: " + p.stderr[-200:]


def morning_text(ctx: Ctx, res: dict, msg: str) -> str:
    """MORNING.md: the one-line verdict, which condition tripped, and where the court came from."""

    def n(x):
        return f"{int(x):,}"

    word = (
        "COVERAGE DEFECT: belongs in the launch gate"
        if res["verdict_defect"]
        else "not a defect for the launch courts by the stated rule"
    )
    rows = {**res["gate"], "All courts": res["overall"]}
    cases = "\n".join(
        f"- {k}: {n(g['whole_missing_english_cases'])} of {n(g['english_cases'])} English cases wholly absent ({g['whole_pct']:.2f}%); scattered chunks {g['scattered_pct']:.2f}% of English chunks"
        for k, g in rows.items()
    )
    tw = ", ".join(res["tripped_whole_cases"]) or "none"
    ts = ", ".join(res["scattered_would_trip"]) or "none"
    cs = res["court_source"]
    return (
        f"# Overnight lane A: finished {time.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"Verdict (by rule, see section 19): **{word}**.\n\n"
        f"The rule binds on WHOLE MISSING CASES (invisible law), 1% of a court's English cases (my threshold). "
        f"Whole-case condition tripped in: **{tw}**. The scattered-chunk rate (does not bind) would have tripped in: {ts}.\n\n{cases}\n\n"
        f"**Court came from the chunk ID, not the label** (CLAUDE.md section 6: a missing label is 0.58% of rows, so a label-based comparison would drop the rows most likely to be absent). "
        f"Ids naming no known court were kept: {n(cs['parquet_rows_id_names_no_court'])} parquet rows. "
        "Qdrant points with no court label (what a label-based run would have lost): "
        + ", ".join(
            f"{c} {n(v)}" for c, v in cs["qdrant_points_without_court_label"].items()
        )
        + ". The parquet label was not read.\n\n"
        "Not on the to-do list: the larger-model single-query-vector comparison. DECISIONS A136 ran it on 250 fresh targets (dense +1.6 @10 replicated, hybrid -0.1 did not); the query model is unchanged. "
        "The only measurement left is the launch-collection real-mixture comparison (gate item 29).\n\n"
        f"Section 19: {msg}.\nFull text: {ctx.home / 'SECTION19.md'}\nFigures: {ctx.home / 'results.json'}, spot-check: {ctx.home / 'spotcheck.json'}\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["all", "parquet", "scan", "analyze", "status"])
    ap.add_argument("--home", default=str(HOME_DEFAULT))
    ap.add_argument(
        "--limit-pages",
        type=int,
        default=None,
        help="testing: stop each scan after this many pages",
    )
    ap.add_argument(
        "--limit-files",
        type=int,
        default=None,
        help="testing: only the first N parquet files",
    )
    ap.add_argument(
        "--partial",
        action="store_true",
        help="analyze even if a scan is incomplete (testing)",
    )
    ap.add_argument("--no-commit", action="store_true")
    a = ap.parse_args()
    ctx = Ctx(Path(a.home))
    if a.stage == "status":
        print(
            ctx.status_path.read_text() if ctx.status_path.exists() else "no status yet"
        )
        return
    try:
        if a.stage in ("all", "parquet"):
            stage_parquet(ctx, a.limit_files)
        if a.stage in ("all", "scan"):
            stage_scan(ctx, COLLECTIONS, a.limit_pages)
        if a.stage in ("all", "analyze"):
            res = stage_analyze(ctx, partial_ok=a.partial)
            spot = stage_spotcheck(ctx, res)
            text = write_section(ctx, res, spot)
            msg = (
                "not committed (--no-commit)"
                if a.no_commit
                else stage_commit(ctx, text)
            )
            ctx.log(f"section 19: {msg}")
            text_m = morning_text(ctx, res, msg)
            (ctx.home / "MORNING.md").write_text(text_m)
            ctx.status(stage="FINISHED", verdict=text_m.split("**")[1])
    except Stop as exc:
        ctx.log(
            f"HARD STOP: {exc}. State is kept; re-run `python scan/coverage_gap.py all` to resume."
        )
        ctx.status(stage="HARD STOP", error=str(exc))
        sys.exit(3)


if __name__ == "__main__":
    main()
