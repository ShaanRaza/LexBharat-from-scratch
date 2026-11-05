"""Measure whether the Court's printed "Case Law Reference" table survives in the text we hold.

Plain words: a judgment in the Court's own law reports prints, on its first page after the headnote, a table of
the cases it cites: one row per cited case, `citation  editor's word  Para N` (for example
`2011 (5) SCR 729   referred to   Para 1`). This script looks for that table in the stored text of
every served case and reports how many cases carry it, how many rows parse, how many were split by the
chunker, which editor words occur, and how many cited cases resolve to a served record.

MEASUREMENT ONLY. Nothing is written to any collection or to the repo's data; nothing is built from it.
The editor's word is NOT interpreted here (that is Phase 2 and needs an advocate); it is counted as text.

Usage: python scan/sc/measure_case_law_table.py SC_TEXT.db OUT.json
Pipeline: none of the 11 steps; offline measurement.
"""

from __future__ import annotations

import collections
import json
import re
import sqlite3
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import measure_refs  # noqa: E402

from core.citator.refs import extract, stored_citation_key  # noqa: E402

HEADING = re.compile(r"c[a-z]{2,4}s?[\s\-]{0,3}l[a-z]w[\s\-]{0,3}ref[a-z]{3,8}", re.I)
START_OF_JUDGMENT = re.compile(
    r"The\s+(?:Judgment|Order)\s+of\s+the\s+Court\s+was\s+delivered|JUDGMENT\s*\n|ORDER\s*\n",
    re.I,
)
# editor words seen in a 600-case reading (referred to, relied on, distinguished, held inapplicable, ...)
WORDS = (
    r"referred\s+to|relied\s+on|retied\s+on|distinguished|distiguished|followed|not\s+followed|approved|"
    r"not\s+approved|cited|overruled|held\s+inapplicable|held\s+applicable|held\s+per\s+incuriam|"
    r"explained|considered|applied|affirmed|doubted|disapproved|dissented|reversed"
)
AFTER = re.compile(
    rf"^[\s,;\-]{{0,4}}(?P<word>{WORDS})\b\.?\s*(?:Paras?\.?\s*(?P<para>[\d][\d,\s\-and]*))?",
    re.I,
)
LOOSE_ROW = re.compile(
    rf"\d{{4}}[\s\S]{{0,70}}?(?:{WORDS})\W{{0,3}}\s*Paras?\.?\s*\d", re.I
)
PAIR_GAP = re.compile(r"\s{0,2}[:=]\s{0,2}")
REGION_CAP = 15000
MAX_IDX = 8  # first nine chunks cover 15,000 characters of a judgment


def build_lookup(db: sqlite3.Connection):
    by_key, by_ysp = {}, collections.defaultdict(list)
    for cid, cit in db.execute("select case_id, citation from ch group by case_id"):
        k = stored_citation_key(cit or "")
        if k:
            by_key[k] = cid
            _, y, supp, _vol, _addl, page = k
            by_ysp[(y, supp, page)].append(cid)
    return by_key, by_ysp


def region_of(text: str) -> str:
    m = START_OF_JUDGMENT.search(text)
    return text[: min(m.start(), REGION_CAP) if m and m.start() > 500 else REGION_CAP]


def rows_in(text: str) -> list[dict]:
    """Every citation immediately followed by an editor word. `with_para` marks the table form."""
    out = []
    for r in extract(text):
        m = AFTER.match(text[r.end : r.end + 80])
        if m:
            out.append(
                {
                    "kind": r.kind,
                    "key": r.key,
                    "word": re.sub(r"\s+", " ", m["word"].lower()),
                    "with_para": bool(m["para"]),
                    "start": r.start,
                }
            )
    return out


def pairs_in(text: str) -> list[tuple]:
    """Two citations joined by a colon or equals sign, one of them SCR: the Court's own parallel
    citation inside a headnote entry (`(2002) 5 SCC 1 : [2002] 3 SCR 810`)."""
    refs = extract(text)
    out = []
    for a, b in zip(refs, refs[1:], strict=False):
        if PAIR_GAP.fullmatch(text[a.end : b.start]):
            kinds = {a.kind, b.kind}
            if "scr" in kinds and len(kinds) == 2:
                other, scr = (a, b) if b.kind == "scr" else (b, a)
                out.append((other.kind, other.key, scr.key))
    return out


def main(db_path: str, out: str) -> None:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    by_key, by_ysp = build_lookup(db)
    cases = [
        r[0] for r in db.execute("select distinct case_id from ch order by case_id")
    ]
    res = collections.Counter()
    words = collections.Counter()
    kinds = collections.Counter()
    resolve = collections.Counter()
    by_decade = collections.defaultdict(collections.Counter)
    examples = []
    pair_kinds = collections.Counter()
    pair_map = collections.defaultdict(collections.Counter)
    for cid in cases:
        rows = db.execute(
            "select chunk_id, idx, cs, ce, text from ch where case_id=? and idx<=?",
            (cid, MAX_IDX),
        ).fetchall()
        text = measure_refs.rebuild(rows)
        reg = re.sub(r"[ \t]+", " ", region_of(text))
        dec = cid[:3] + "0s"
        by_decade[dec]["cases"] += 1
        head = HEADING.search(reg)
        rs = rows_in(reg)
        loose = LOOSE_ROW.search(reg)
        if head and loose:
            res["heading_with_some_row_text"] += 1
        if head and not loose:
            res["heading_with_no_row_text_at_all"] += 1
        prs = pairs_in(reg)
        if prs:
            res["cases_with_headnote_parallel_pair"] += 1
            by_decade[dec]["pair_cases"] += 1
        for kind, okey, skey in prs:
            res["headnote_parallel_pairs"] += 1
            pair_kinds[kind] += 1
            _, y, supp, vol, _a, page = skey
            tgt = (
                by_key.get(("scr", y, supp, vol, False, page))
                if vol is not None
                else None
            )
            pair_map[(kind, okey)][tgt or "unresolved_scr"] += 1
        table = [r for r in rs if r["with_para"]]
        if head:
            res["heading_cases"] += 1
            by_decade[dec]["heading"] += 1
        if table:
            res["table_cases"] += 1
            by_decade[dec]["table"] += 1
        if rs and not table:
            res["headnote_style_only_cases"] += 1
        if table and not head:
            res["table_rows_without_heading_cases"] += 1
        if head and not table:
            res["heading_but_no_rows_cases"] += 1
            if len(examples) < 6:
                examples.append(
                    (cid, reg[head.start() : head.start() + 300].replace("\n", "|"))
                )
        # chunk breakage: is every table row inside ONE stored chunk with the heading?
        if head and table:
            per = []
            for _chunk_id, _idx, _cs, _ce, t in rows:
                tt = re.sub(
                    r"[ \t]+",
                    " ",
                    zlib.decompress(t).decode() if isinstance(t, bytes) else t,
                )
                per.append(
                    (
                        bool(HEADING.search(tt)),
                        len([x for x in rows_in(tt) if x["with_para"]]),
                    )
                )
            full = len(table)
            best = max((n for h, n in per if h), default=0)
            if best >= full:
                res["table_whole_in_heading_chunk"] += 1
            else:
                res["table_split_across_chunks_or_pages"] += 1
        for r in table:
            res["table_rows"] += 1
            words[r["word"]] += 1
            kinds[r["kind"]] += 1
            by_decade[dec]["rows"] += 1
            if r["kind"] == "scr":
                k = r["key"]
                _, y, supp, vol, _a, page = k
                if vol is not None:
                    tgt = by_key.get(("scr", y, supp, vol, False, page))
                    resolve["scr_exact" if tgt else "scr_unresolved"] += 1
                else:
                    c = by_ysp.get((y, supp, page), [])
                    resolve[
                        "scr_volume_omitted_unique" if len(c) == 1 else "scr_unresolved"
                    ] += 1
                if tgt_ok := (
                    by_key.get(("scr", y, supp, vol, False, page))
                    if vol is not None
                    else None
                ):
                    resolve["_self" if tgt_ok == cid else "_other"] += 1
            else:
                resolve[f"{r['kind']}_not_resolvable_here"] += 1
    summ = collections.Counter()
    for (kind, _okey), c in pair_map.items():
        tg = {t for t in c if t != "unresolved_scr"}
        summ[f"{kind}_keys_with_pair"] += 1
        if len(tg) == 1 and "unresolved_scr" not in c:
            summ[f"{kind}_keys_unique_resolved_target"] += 1
        elif len(tg) > 1:
            summ[f"{kind}_keys_conflicting_targets"] += 1
        elif not tg:
            summ[f"{kind}_keys_scr_side_not_held"] += 1
    keys_in_corpus = {"scc": set(), "air": set()}
    for cid_, b in db.execute("select case_id, text from ch"):
        t = zlib.decompress(b).decode() if isinstance(b, bytes) else b
        for r in extract(t):
            if r.kind in keys_in_corpus:
                keys_in_corpus[r.kind].add(r.key)
    for kind, ks in keys_in_corpus.items():
        mapped = {k for (kd, k) in pair_map if kd == kind}
        uniq = {
            k
            for (kd, k), c in pair_map.items()
            if kd == kind
            and len({t for t in c if t != "unresolved_scr"}) == 1
            and "unresolved_scr" not in c
        }
        summ[f"{kind}_distinct_keys_in_corpus"] = len(ks)
        summ[f"{kind}_corpus_keys_with_any_pair"] = len(ks & mapped)
        summ[f"{kind}_corpus_keys_with_unique_resolved_pair"] = len(ks & uniq)
    Path(out).write_text(
        json.dumps(
            {
                "cases": len(cases),
                "counts": dict(res),
                "pair_kinds": dict(pair_kinds),
                "pair_summary": dict(summ),
                "words": words.most_common(30),
                "row_kinds": dict(kinds),
                "resolve": dict(resolve),
                "by_decade": {k: dict(v) for k, v in sorted(by_decade.items())},
                "heading_no_rows_examples": examples,
            },
            indent=1,
            default=str,
        )
    )
    print(json.dumps(dict(res), indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
