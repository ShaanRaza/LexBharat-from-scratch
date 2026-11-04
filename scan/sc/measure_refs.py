#!/usr/bin/env python3
"""SC lane, Task 3b to 3d: how many citation-shaped references do SC judgments hold, how many
resolve to a stored record, and how many cite by case name only?

Plain words: reads the local sqlite copy made by dump_text.py (never Qdrant), rebuilds each judgment's text
from its overlapping chunks, finds references with core/citator/refs.py, and tries to match each to a served
case. Nothing is written except the JSON result file. No network, no vendor call, no cost.

    python scan/sc/measure_refs.py SC_TEXT.db OUT.json [LIMIT_CASES]

Resolution rules (all exact; nothing is fuzzy-matched):
  scr      key (year, supp, volume, addl, first page) equals a stored `citation` field
  neutral  `YYYY INSC N` equals a served case_id `YYYY_INSC_N`
  scc/air/scc_online/other: NOT resolvable from the stored field (it holds SCR only). Counted, and a
           concordance learned from parallel citations in the same text is measured separately as
           "derived", never mixed into the direct rate.

Touches none of the 11 pipeline steps and none of the four verifier checks.
"""

from __future__ import annotations

import bisect
import collections
import json
import re
import signal
import sqlite3
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.citator.refs import Ref, extract, neutral_case_id, stored_citation_key  # noqa: E402

HEADER_WORDS = re.compile(r"SUPREME\s+COURT\s+REPORTS", re.I)
V_ANCHOR = re.compile(r"\s(?:v\.|vs\.?|versus|Vs\.?)\s")
_NAME_WORD = re.compile(
    r"[A-Z][\w.'’\-]*|of|and|the|&|for|ors\.?|anr\.?|another|others|etc\.?|\(P\)"
)
MAX_NAME_WORDS = 7  # per side; windowed, so no regex backtracking on long capital runs


def name_pairs(text: str):
    """Yield (start, end, left, right) for 'A v. B' mentions. Words are taken outward from the 'v.' one at a
    time, so cost is linear in the text (a nested-repeat regex hung on one long judgment)."""
    for m in V_ANCHOR.finditer(text):
        left_words: list[str] = []
        pos = m.start()
        for w in reversed(text[max(0, pos - 160) : pos].split()):
            if not _NAME_WORD.fullmatch(w) or len(left_words) >= MAX_NAME_WORDS:
                break
            left_words.append(w)
        right_words: list[str] = []
        end = m.end()
        for w in text[end : end + 160].split():
            if not _NAME_WORD.fullmatch(w) or len(right_words) >= MAX_NAME_WORDS:
                break
            right_words.append(w)
        if not left_words or not right_words:
            continue
        if not (left_words[0][:1].isupper() or left_words[0][:1] == "("):
            continue
        if not right_words[0][:1].isupper():
            continue
        left = " ".join(reversed(left_words))
        right = " ".join(right_words)
        yield pos - len(left), end + len(right) + 1, left, right


def body_of(text: str) -> str:
    return text.split("\n\n", 1)[1] if "\n\n" in text else text


def rebuild(chunks: list[tuple]) -> str:
    """Whole judgment text from its chunks. body length equals char_end - char_start exactly (measured),
    so the overlap with the previous chunk is dropped by offset and positions are exact."""
    seen: set[str] = set()
    parts: list[str] = []
    end = 0
    for chunk_id, _idx, cs, ce, blob in sorted(
        chunks, key=lambda c: c[1] if c[1] is not None else 0
    ):
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        body = body_of(zlib.decompress(blob).decode())
        skip = max(0, end - (cs or 0))
        parts.append(body[skip:])
        end = max(end, ce or 0)
    return "".join(parts)


def norm_name(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def main(db_path: str, out: str, limit: str | None = None) -> None:
    db = sqlite3.connect(db_path)
    db.execute("create index if not exists ch_case on ch(case_id)")
    meta: dict[str, dict] = {}
    for cid, cit, title, year in db.execute(
        "select case_id, citation, title, year from ch group by case_id"
    ):
        meta[cid] = {"cit": cit, "title": title, "year": year}
    served = set(meta)

    # volume index from the stored citation field
    by_key: dict[tuple, str] = {}
    vol_pages: dict[tuple, list[tuple[int, str]]] = collections.defaultdict(list)
    own_key: dict[str, tuple] = {}
    for cid, m in meta.items():
        k = stored_citation_key(m["cit"])
        if not k:
            continue
        by_key[k] = cid
        own_key[cid] = k
        vol_pages[k[:5]].append((k[5], cid))
    for v in vol_pages.values():
        v.sort()
    starts = {v: [p for p, _ in lst] for v, lst in vol_pages.items()}
    by_vol_nopage = {
        (k[1], k[2], k[3]): 1 for k in by_key
    }  # (year, supp, vol) held at all
    by_ysp: dict[tuple, list[str]] = collections.defaultdict(list)
    for k, c in by_key.items():
        by_ysp[(k[1], k[2], k[5])].append(c)

    cases = sorted(served)
    if limit:
        cases = cases[: int(limit)]

    global G
    G = dict(
        db_path=db_path,
        meta=meta,
        served=served,
        by_key=by_key,
        by_ysp=by_ysp,
        vol_pages=vol_pages,
        starts=starts,
        vol_any=by_vol_nopage,
        own_key=own_key,
    )
    import multiprocessing as mp

    workers = 6
    shards = [cases[i::workers] for i in range(workers)]
    with mp.get_context("fork").Pool(workers) as pool:
        parts = pool.map(_shard, shards)
    res = _new_res()
    scc_pairs: dict[tuple, collections.Counter] = collections.defaultdict(
        collections.Counter
    )
    air_pairs: dict[tuple, collections.Counter] = collections.defaultdict(
        collections.Counter
    )
    standalone: list[tuple[str, tuple, str]] = []
    name_examples: list[str] = []
    for pr, sp, ap, sa, ne in parts:
        _merge(res, pr)
        for k, c in sp.items():
            scc_pairs[k].update(c)
        for k, c in ap.items():
            air_pairs[k].update(c)
        standalone += sa
        name_examples += ne
    res.pop("_last_artifact", None)

    # derived concordance: how many standalone SCC / AIR references could be placed through a pair?
    der = {"scc": collections.Counter(), "air": collections.Counter()}
    for kind, key, cid in standalone:
        pairs = (scc_pairs if kind == "scc" else air_pairs).get(key)
        if kind == "air" and key[2] != "SC":
            der[kind]["not_supreme_court"] += 1
        elif not pairs:
            der[kind]["no_pair_anywhere"] += 1
        elif len(pairs) > 1:
            der[kind]["conflicting_pairs"] += 1
        else:
            der[kind]["resolvable_via_pair"] += 1
    res["derived"] = {
        k: dict(v, standalone=sum(v.values())) for k, v in der.items()
    } | {
        "scc_keys_with_pair": len(scc_pairs),
        "scc_keys_conflicting": sum(1 for c in scc_pairs.values() if len(c) > 1),
        "air_keys_with_pair": len(air_pairs),
        "air_keys_conflicting": sum(1 for c in air_pairs.values() if len(c) > 1),
    }
    res.pop("_last_artifact", None)
    res["name_examples"] = name_examples[:40]
    out_obj = {
        k: (dict(v) if isinstance(v, collections.Counter) else v)
        for k, v in res.items()
    }
    out_obj["scr_by_era"] = {k: dict(v) for k, v in res["scr_by_era"].items()}
    out_obj["kind_by_era"] = {k: dict(v) for k, v in res["kind_by_era"].items()}
    out_obj["unresolved_examples"] = dict(res["unresolved_examples"])
    Path(out).write_text(json.dumps(out_obj, indent=1, default=str))
    print(
        json.dumps(
            {
                k: out_obj[k]
                for k in (
                    "cases",
                    "chars",
                    "mentions",
                    "distinct",
                    "scr",
                    "neutral",
                    "names",
                )
            },
            indent=1,
        )
    )


G: dict = {}


class _CaseTimeout(Exception):
    pass


def _on_alarm(_signum, _frame) -> None:
    raise _CaseTimeout


def _new_res() -> dict:
    return {
        "cases": 0,
        "cases_with_gap": 0,
        "chars": 0,
        "mentions": collections.Counter(),  # kind -> every printed reference
        "distinct": collections.Counter(),  # kind -> distinct (case, key)
        "air_note": collections.Counter(),
        "scr": collections.Counter(),
        "neutral": collections.Counter(),
        "kind_by_era": collections.defaultdict(collections.Counter),
        "scr_by_era": collections.defaultdict(collections.Counter),
        "unresolved_examples": collections.defaultdict(list),
        "names": collections.Counter(),
        "inbound": collections.Counter(),  # target case_id -> number of distinct citing cases
        "timed_out": collections.Counter(),  # case_id -> 1 when the 60 s alarm fired
    }


def _merge(into: dict, part: dict) -> None:
    for k, v in part.items():
        if isinstance(v, int):
            into[k] = into.get(k, 0) + v
        elif isinstance(v, collections.Counter):
            into[k].update(v)
        elif k in ("scr_by_era", "kind_by_era"):
            for e, c in v.items():
                into[k][e].update(c)
        elif k == "unresolved_examples":
            for b, lst in v.items():
                into[k][b] += lst[: max(0, 25 - len(into[k][b]))]


def _shard(cases: list[str]):
    g = G
    meta, served, by_key, by_ysp = g["meta"], g["served"], g["by_key"], g["by_ysp"]
    vol_pages, starts, own_key = g["vol_pages"], g["starts"], g["own_key"]
    by_vol_nopage = g["vol_any"]
    db = sqlite3.connect(g["db_path"])
    res = _new_res()
    scc_pairs: dict[tuple, collections.Counter] = collections.defaultdict(
        collections.Counter
    )
    air_pairs: dict[tuple, collections.Counter] = collections.defaultdict(
        collections.Counter
    )
    standalone: list[tuple[str, tuple, str]] = []
    name_examples: list[str] = []
    q = "select chunk_id, idx, cs, ce, text from ch where case_id=? "

    def one(cid: str) -> None:
        rows = db.execute(q, (cid,)).fetchall()
        idxs = sorted({r[1] for r in rows if r[1] is not None})
        if idxs and idxs != list(range(idxs[0], idxs[0] + len(idxs))):
            res["cases_with_gap"] += 1
        text = rebuild(rows)
        res["cases"] += 1
        res["kind_by_era"][
            (
                "pre1990"
                if int(cid[:4]) < 1990
                else ("1990-2009" if int(cid[:4]) < 2010 else "2010+")
            )
        ]["_cases"] += 1
        res["chars"] += len(text)
        refs = extract(text)
        okey = own_key.get(cid)
        era = (
            "pre1990"
            if int(cid[:4]) < 1990
            else ("1990-2009" if int(cid[:4]) < 2010 else "2010+")
        )
        seen: set[tuple] = set()
        resolved_scr_positions: list[tuple[int, str]] = []
        cites_out: set[str] = set()
        for r in refs:
            res["mentions"][r.kind] += 1
            res["kind_by_era"][era][r.kind] += 1
            if (r.kind, r.key) not in seen:
                seen.add((r.kind, r.key))
                res["distinct"][r.kind] += 1
            if r.kind == "air":
                res["air_note"][r.note] += 1
            if r.kind == "scr":
                _classify_scr(
                    r,
                    text,
                    cid,
                    okey,
                    by_key,
                    by_ysp,
                    vol_pages,
                    starts,
                    by_vol_nopage,
                    res,
                    era,
                )
                tgt = _lookup(r.key, by_key, by_ysp)[0]
                if tgt and tgt != cid and not res["_last_artifact"]:
                    resolved_scr_positions.append((r.start, tgt))
                    cites_out.add(tgt)
            elif r.kind == "neutral":
                _, y, num = r.key
                tgt = neutral_case_id(y, num)
                if tgt == cid:
                    res["neutral"]["self"] += 1
                elif tgt in served:
                    res["neutral"]["resolved"] += 1
                    cites_out.add(tgt)
                else:
                    res["neutral"]["unresolved"] += 1
                    _example(res, "neutral_unresolved", r.raw, cid)
        for t in cites_out:
            res["inbound"][t] += 1
        # parallel citations: an SCC/AIR printed within 90 characters of a resolved SCR
        for r in refs:
            if r.kind not in ("scc", "air"):
                continue
            near = [t for p, t in resolved_scr_positions if abs(p - r.start) <= 90]
            if near:
                (scc_pairs if r.kind == "scc" else air_pairs)[r.key][near[0]] += 1
            else:
                standalone.append((r.kind, r.key, cid))
        _names(text, refs, meta[cid]["title"] or "", res, name_examples)

    # A pattern that backtracks without end on one odd text hung a whole run for hours (4 Nov 2026).
    # Each case gets a 60 s alarm; a case that trips it is counted in `timed_out`, never skipped silently.
    signal.signal(signal.SIGALRM, _on_alarm)
    for cid in cases:
        signal.setitimer(signal.ITIMER_REAL, 60)
        try:
            one(cid)
        except _CaseTimeout:
            res["timed_out"][cid] += 1
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)

    return res, scc_pairs, air_pairs, standalone, name_examples


def _lookup(key: tuple, by_key: dict, by_ysp: dict) -> tuple[str | None, str]:
    """Exact match on (year, supp, volume, page). A reference that omits the volume (`[1950] S.C.R. 88`,
    common before 1955) matches only when exactly one stored case in that year has that first page."""
    _, y, supp, vol, _addl, page = key
    if vol is not None:
        c = by_key.get(("scr", y, supp, vol, False, page))
        return (c, "exact") if c else (None, "none")
    cands = by_ysp.get((y, supp, page), [])
    if len(cands) == 1:
        return cands[0], "volume_omitted"
    return (None, "ambiguous") if cands else (None, "none")


def _example(res: dict, bucket: str, raw: str, cid: str) -> None:
    lst = res["unresolved_examples"][bucket]
    if len(lst) < 25:
        lst.append(f"{cid}: {raw}")


def _classify_scr(
    r: Ref, text, cid, okey, by_key, by_ysp, vol_pages, starts, vol_any, res, era
) -> None:
    _, y, supp, vol, addl, page = r.key
    ctx = text[max(0, r.start - 70) : r.end + 20]
    res["_last_artifact"] = False
    tgt, how = _lookup(r.key, by_key, by_ysp)
    sc = res["scr"]
    # running page header of the judgment's own volume ("<court> REPORTS [2000] 3 S.C.R. 830")
    if okey and r.key[:5] == okey[:5]:
        s = starts[okey[:5]]
        i = bisect.bisect_left(s, okey[5])
        nxt = s[i + 1] if i + 1 < len(s) else okey[5] + 400
        if okey[5] - 1 <= page <= nxt:
            res["_last_artifact"] = True
            sc["own_volume_page_in_own_range (running header, not a citation)"] += 1
            return
    if HEADER_WORDS.search(ctx):
        res["_last_artifact"] = True
        sc["beside_SUPREME_COURT_REPORTS_header"] += 1
        return
    if tgt == cid:
        sc["self"] += 1
        return
    res["scr_by_era"][era]["refs"] += 1
    if how == "ambiguous":
        sc["unresolved: volume_omitted_and_page_matches_several_volumes"] += 1
        res["scr_by_era"][era]["unresolved"] += 1
        _example(res, "ambiguous_volume", r.raw, cid)
        return
    if tgt:
        sc[
            "resolved" if how == "exact" else "resolved_volume_omitted_unique_by_page"
        ] += 1
        res["scr_by_era"][era]["resolved"] += 1
        return
    vk = r.key[:5]
    if y < 1950 or y > 2025:
        b = "year_outside_1950_2025"
    elif vk in vol_pages:
        pages = starts[vk]
        i = bisect.bisect_right(pages, page) - 1
        if i >= 0 and i + 1 < len(pages) and page < pages[i + 1]:
            b = "page_inside_a_held_case (pinpoint page cited as first page?)"
        elif i + 1 >= len(pages):
            b = "volume_held_page_after_last_held_case"
        else:
            b = "volume_held_page_not_a_start"
    elif (y, supp, vol) in vol_any:
        b = "volume_held_other_addl_flag"
    else:
        alt = [
            yy for yy in (y - 1, y + 1) if ("scr", yy, supp, vol, addl, page) in by_key
        ]
        b = "year_off_by_one_would_match" if alt else "volume_not_held_at_all"
    sc["unresolved: " + b] += 1
    res["scr_by_era"][era]["unresolved"] += 1
    _example(res, b, r.raw, cid)


_YEAR_BRACKET = re.compile(r"[\[\(]\s*(?:18|19|20)\d\d\s*[\]\)]")
_FOOTNOTE = re.compile(r"[\s,]*[\(\[]\s*\d{1,2}\s*[\)\]]")


def _upper_share(s: str) -> float:
    letters = [c for c in s if c.isalpha()]
    return sum(c.isupper() for c in letters) / len(letters) if letters else 0.0


def _names(
    text: str, refs: list[Ref], title: str, res: dict, examples: list[str]
) -> None:
    """3d. 'A v. B' mentions, bucketed by what stands next to the name (within 160 characters after it, or
    100 before it): a citation this module extracts, any other bracketed-year citation (foreign or other
    reporters), a footnote marker (the citation is printed at the page foot), or nothing (name only).
    Page captions (mostly capitals) and the case's own caption are skipped."""
    starts = [r.start for r in refs]
    own = norm_name(title)[:24]
    seen: set[str] = set()
    n = res["names"]
    for m_start, m_end, left, right in name_pairs(text):
        nm = norm_name(left)
        if _upper_share(left + right) >= 0.8:
            n["page_caption_skipped"] += 1
            continue
        if own and (nm[:12] in own or own[:12] in nm):
            n["own_caption_skipped"] += 1
            continue
        i = bisect.bisect_left(starts, m_end - 1)
        extracted = i < len(starts) and starts[i] - m_end <= 160
        j = bisect.bisect_left(starts, m_start) - 1
        extracted = extracted or (j >= 0 and m_start - refs[j].end <= 100)
        after = text[m_end : m_end + 160]
        if extracted:
            bucket = "with_extracted_citation"
        elif _YEAR_BRACKET.search(after):
            bucket = "with_other_year_citation"
        elif _FOOTNOTE.match(text[m_end : m_end + 14]):
            bucket = "with_footnote_marker"
        else:
            bucket = "name_only"
        n["mentions"] += 1
        n["mentions_" + bucket] += 1
        key = nm[:20] + "|" + norm_name(right)[:20]
        if key not in seen:
            seen.add(key)
            n["distinct"] += 1
            n["distinct_" + bucket] += 1
            if bucket == "name_only" and n["distinct_name_only"] % 600 == 0:
                examples.append(f"{cid_hint(title)}: {left} v. {right}")


def cid_hint(title: str) -> str:
    return (title or "")[:30]


if __name__ == "__main__":
    main(*sys.argv[1:])
