#!/usr/bin/env python3
"""Citator Phase 1 build: the links between served Supreme Court judgments, with and without the pair map.

Plain words: reads the local sqlite copy made by dump_text.py (never Qdrant), and for every served
judgment finds the references to other served judgments. A reference is tied to a record in one of two
ways, and the two are kept apart in the output:

  direct  an SCR citation equal to a stored `citation` field, or a neutral citation (`2018 INSC 329`)
  mapped  an SCC citation, or an AIR Supreme Court citation, placed through the headnote pair map
          (core/citator/pairmap.py: printed by at least 2 independent judgments, twice the runner-up)

It writes three files into OUT_DIR and prints the link-density report:

  links.jsonl.gz  one line per (citing, cited) pair: citing, cited, via, mentions
  pairmap.json    the trusted map, so a reader can see exactly what was trusted
  density.json    inbound links per case before (direct only) and after (direct + mapped)

A case with no link in links.jsonl has none we could read. That is a limit of the data, never clearance
(core/citator/links.py). Nothing is written to a collection or the repo's data, no network, no cost.

    python scan/sc/build_links.py SC_TEXT.db OUT_DIR [--validate scan/sc/judges_library_landmark.json]
    SC_TEXT.db is the `sc_text2.db` form of dump_text.py (it carries citation, title and year).

Pipeline: none of the 11 steps; offline data work. Touches no verifier check.
"""

from __future__ import annotations

import collections
import gzip
import json
import multiprocessing as mp
import re
import signal
import sqlite3
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import measure_case_law_table as t  # noqa: E402
import measure_refs as mr  # noqa: E402

from core.citator.links import Link, Via, group_inbound  # noqa: E402
from core.citator.pairmap import build_map  # noqa: E402
from core.citator.refs import extract, neutral_case_id, stored_citation_key  # noqa: E402

CASE_SECONDS = (
    60  # a pattern that backtracks on one odd text must not hang the run (4 Nov 2026)
)
G: dict = {}


class _Timeout(Exception):
    pass


def _alarm(_s, _f) -> None:
    raise _Timeout


def _case(cid: str, db: sqlite3.Connection) -> dict:
    g = G
    rows = db.execute(
        "select chunk_id, idx, cs, ce, text from ch where case_id=?", (cid,)
    ).fetchall()
    text = mr.rebuild(rows)
    refs = extract(text)
    scratch = (
        mr._new_res()
    )  # _classify_scr counts into it; only its artifact flag is used here
    era = "pre1990" if int(cid[:4]) < 1990 else "1990+"
    direct: collections.Counter[str] = collections.Counter()
    standalone: collections.Counter[tuple] = collections.Counter()
    for r in refs:
        if r.kind == "scr":
            mr._classify_scr(
                r, text, cid, g["own_key"].get(cid), g["by_key"], g["by_ysp"],
                g["vol_pages"], g["starts"], g["vol_any"], scratch, era,
            )  # fmt: skip
            tgt = mr._lookup(r.key, g["by_key"], g["by_ysp"])[0]
            if tgt and tgt != cid and not scratch["_last_artifact"]:
                direct[tgt] += 1
        elif r.kind == "neutral":
            tgt = neutral_case_id(r.key[1], r.key[2])
            if tgt != cid and tgt in g["served"]:
                direct[tgt] += 1
        elif r.kind in ("scc", "air"):
            standalone[r.key] += 1
    # the headnote pairs this judgment prints (evidence for the map), own pair removed
    pairs = []
    head = [r for r in rows if r[1] is not None and r[1] <= t.MAX_IDX]
    region = re.sub(r"[ \t]+", " ", t.region_of(mr.rebuild(head)))
    for kind, okey, skey in t.pairs_in(region):
        if kind in ("scc", "air") and skey[3] is not None:
            tgt = g["by_key"].get(("scr", skey[1], skey[2], skey[3], False, skey[5]))
            if tgt and tgt != cid:
                pairs.append((okey, tgt))
    return {"direct": dict(direct), "standalone": dict(standalone), "pairs": pairs}


def _shard(cases: list[str]) -> tuple[dict[str, dict], list[str]]:
    db = sqlite3.connect(f"file:{G['db']}?mode=ro", uri=True)
    out: dict[str, dict] = {}
    timed_out: list[str] = []
    signal.signal(signal.SIGALRM, _alarm)
    for cid in cases:
        signal.setitimer(signal.ITIMER_REAL, CASE_SECONDS)
        try:
            out[cid] = _case(cid, db)
        except _Timeout:
            timed_out.append(cid)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
    return out, timed_out


def _lookups(db: sqlite3.Connection) -> None:
    meta = {
        cid: (cit, title)
        for cid, cit, title in db.execute(
            "select case_id, citation, title from ch group by case_id"
        )
    }
    by_key, own_key = {}, {}
    vol_pages: dict[tuple, list] = collections.defaultdict(list)
    by_ysp: dict[tuple, list] = collections.defaultdict(list)
    for cid, (cit, _title) in meta.items():
        k = stored_citation_key(cit or "")
        if k:
            by_key[k], own_key[cid] = cid, k
            vol_pages[k[:5]].append((k[5], cid))
            by_ysp[(k[1], k[2], k[5])].append(cid)
    for v in vol_pages.values():
        v.sort()
    G.update(
        meta=meta, served=set(meta), by_key=by_key, own_key=own_key,
        vol_pages=vol_pages, by_ysp=by_ysp,
        starts={v: [p for p, _ in lst] for v, lst in vol_pages.items()},
        vol_any={(k[1], k[2], k[3]): 1 for k in by_key},
    )  # fmt: skip


def validate(trusted: dict, truth_path: str) -> dict:
    """Judges Library landmark table: each row names an SCR record and its SCC citation."""
    right = wrong = missing = untestable = 0
    for _n, scr_key, _label, sccs in json.loads(Path(truth_path).read_text()):
        record = G["by_key"].get(tuple(scr_key)) if scr_key else None
        if not record or not sccs:
            untestable += 1
            continue
        for key, _text in sccs:
            got = trusted.get(tuple(key))
            if got is None:
                missing += 1
            elif got == record:
                right += 1
            else:
                wrong += 1
    return {
        "right": right,
        "wrong": wrong,
        "not_covered": missing,
        "untestable_rows": untestable,
    }


BUCKETS = [(0, 0), (1, 1), (2, 2), (3, 5), (6, 10), (11, 50), (51, 200), (201, 10**9)]


def distribution(counts: list[int]) -> dict:
    s = sorted(counts)
    n = len(s)

    def pct(p: float) -> int:
        return s[min(n - 1, int(p * n))]

    top = s[-(n // 100) :]
    return {
        "cases": n,
        "with_a_readable_link": sum(1 for c in s if c),
        "share_with_a_readable_link": round(sum(1 for c in s if c) / n, 4),
        "links": sum(s),
        "mean": round(statistics.fmean(s), 3),
        "median": statistics.median(s),
        "p75": pct(0.75), "p90": pct(0.90), "p99": pct(0.99), "max": s[-1],
        "cases_with_2_or_more": sum(1 for c in s if c >= 2),
        "cases_with_3_or_more": sum(1 for c in s if c >= 3),
        "share_held_by_top_1_percent": round(sum(top) / sum(s), 4) if sum(s) else 0,
        "buckets": {
            (f"{lo}" if lo == hi else f"{lo}-{hi}" if hi < 10**9 else f"{lo}+"): sum(1 for c in s if lo <= c <= hi)
            for lo, hi in BUCKETS
        },
    }  # fmt: skip


def report(before: dict[str, int], after: dict[str, int], served: set[str]) -> dict:
    ids = sorted(served)
    b = [before.get(c, 0) for c in ids]
    a = [after.get(c, 0) for c in ids]
    by_decade: dict[str, dict] = {}
    for dec in range(1950, 2030, 10):
        sub = [i for i, c in enumerate(ids) if dec <= int(c[:4]) < dec + 10]
        if sub:
            by_decade[f"{dec}s"] = {
                "cases": len(sub),
                "before_mean": round(statistics.fmean(b[i] for i in sub), 3),
                "after_mean": round(statistics.fmean(a[i] for i in sub), 3),
                "before_share_with_2_or_more": round(
                    sum(1 for i in sub if b[i] >= 2) / len(sub), 4
                ),
                "after_share_with_2_or_more": round(
                    sum(1 for i in sub if a[i] >= 2) / len(sub), 4
                ),
            }
    return {
        "before_direct_only": distribution(b),
        "after_with_pair_map": distribution(a),
        "cases_that_gained_a_first_link": sum(1 for x, y in zip(b, a, strict=True) if x == 0 and y > 0),
        "cases_that_gained_links": sum(1 for x, y in zip(b, a, strict=True) if y > x),
        "cases_that_reached_2_or_more": sum(1 for x, y in zip(b, a, strict=True) if x < 2 <= y),
        "by_decade_of_cited_case": by_decade,
    }  # fmt: skip


def main(db_path: str, out_dir: str, truth: str | None = None) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    _lookups(db)
    G["db"] = db_path
    cases = sorted(G["served"])
    with mp.get_context("fork").Pool(6) as pool:
        parts = pool.map(_shard, [cases[i::6] for i in range(6)])
    per_case: dict[str, dict] = {}
    timed_out: list[str] = []
    for done, slow in parts:
        per_case.update(done)
        timed_out += slow

    evidence: dict[tuple, dict[str, set[str]]] = collections.defaultdict(
        lambda: collections.defaultdict(set)
    )
    for cid, r in per_case.items():
        for key, tgt in r["pairs"]:
            evidence[key][tgt].add(cid)
    trusted = build_map(evidence)

    direct_links: dict[tuple[str, str], int] = {}
    mapped_links: dict[tuple[str, str], int] = collections.defaultdict(int)
    for cid, r in per_case.items():
        for tgt, n in r["direct"].items():
            direct_links[(cid, tgt)] = n
        for key, n in r["standalone"].items():
            tgt = trusted.get(key)
            if tgt and tgt != cid:
                mapped_links[(cid, tgt)] += n
    links = [Link(c, d, Via.DIRECT, n) for (c, d), n in direct_links.items()]
    links += [
        Link(c, d, Via.MAPPED, n)
        for (c, d), n in mapped_links.items()
        if (c, d) not in direct_links
    ]

    after = {c: g.readable for c, g in group_inbound(links).items()}
    before = {
        c: g.readable
        for c, g in group_inbound(x for x in links if x.via is Via.DIRECT).items()
    }

    # mtime=0 so the same links give the same bytes, and a rebuild shows up as a real diff
    with gzip.GzipFile(out / "links.jsonl.gz", "wb", mtime=0) as gz:
        for lk in sorted(links, key=lambda x: (x.cited, x.citing)):
            row = {"citing": lk.citing, "cited": lk.cited, "via": lk.via.value}
            row["mentions"] = lk.mentions
            gz.write((json.dumps(row) + "\n").encode())
    (out / "pairmap.json").write_text(
        json.dumps(sorted([list(k), v] for k, v in trusted.items()), indent=0)
    )
    rep = report(before, after, G["served"])
    rep["map"] = {
        "keys_trusted": len(trusted),
        "scc": sum(1 for k in trusted if k[0] == "scc"),
        "air": sum(1 for k in trusted if k[0] == "air"),
    }
    rep["timed_out"] = timed_out
    rep["links"] = {
        "direct": len(direct_links),
        "mapped_only": len(links) - len(direct_links),
    }
    if truth:
        rep["validation_against_judges_library"] = validate(trusted, truth)
    (out / "density.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    args = sys.argv[1:]
    truth_arg = args[args.index("--validate") + 1] if "--validate" in args else None
    main(args[0], args[1], truth_arg)
