"""How much does the verifier's named-case key protect? (A113, result A115)

Verifier check 1 (core/verify.py, `_unretrieved_authority`) reduces a case name written
in an answer to ONE word either side of "v" and accepts it as retrieved if that
"<word> v <word>" appears in the title or text of any retrieved passage. In Indian
case law the right-hand word is dominated by "Union of India", "State of X" and
"Commissioner", so the key may carry little information. This file counts it.

It changes nothing in core/. It IMPORTS the verifier's own `_VERSUS_CORE` and
`_norm_case_name` (a measurement that reimplements the thing under test measures
something else), and a test checks they are the same objects. It then cross-checks
its key against the verifier itself: for pairs of different titles it asks the real
`_unretrieved_authority` whether naming B is accepted when only A was retrieved.

INPUT. A file of records with a `title` field (and optionally `text`): .jsonl or
.jsonl.gz, .csv, or .parquet. The default is the practice fixtures (1,398 records),
which are a SAMPLE, not the corpus. The same command runs on a full title dump:

    .venv/bin/python -m evals.title_keys                       # practice fixtures
    .venv/bin/python -m evals.title_keys --titles dump.parquet --out keys.json

WHAT IT DOES NOT SHOW. It measures how often two different real titles share a key,
as a stand-in for "an invented name shares a key with something retrieved". Real
retrieval is topical, not random, so the reach numbers are a first approximation.
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from math import comb
from pathlib import Path
from typing import Any

from core.contracts import Passage
from core.verify import (
    _VERSUS_CORE,
    _norm_case_name,
    _unretrieved_authority,
    normalise,
)

HERE = Path(__file__).parent
PRACTICE = HERE.parent / "tests" / "fixtures" / "practice"
COMMON_RIGHT = ("union", "state", "commissioner")

# --- 1. The key: exactly what the verifier derives -----------------------------------


def keys_of(text: str) -> list[str]:
    """Every "<word> v <word>" key the verifier would derive from `text`. Titles write
    "versus"; `_norm_case_name` makes that "v" first, as the verifier does."""
    out = []
    for m in _VERSUS_CORE.finditer(_norm_case_name(text)):
        left, right = normalise(m.group(1)), normalise(m.group(2))
        if not left or not right or left.isdigit() or right.isdigit():
            continue  # the verifier skips these too ("Article 14 v. 19")
        out.append(_norm_case_name(f"{left} v {right}"))
    return out


def right_token(key: str) -> str:
    return key.split(" v ", 1)[1]


# --- 2. Reading records --------------------------------------------------------------


def read_records(path: Path) -> list[dict[str, Any]]:
    name = path.name
    if name.endswith(".parquet"):
        import pyarrow.parquet as pq  # only for this file type

        return pq.read_table(path).to_pylist()
    if ".csv" in name:
        import csv

        with open(path, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    opener = gzip.open if name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def default_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in ("chunks", "act_sections"):
        rows += read_records(PRACTICE / f"{name}.jsonl.gz")
    return rows


# --- 3. The measurement --------------------------------------------------------------


def _share(n: int, d: int) -> float:
    return round(n / d, 4) if d else 0.0


def reach(shared_others: int, others: int, k: int) -> float:
    """P(at least one of k randomly retrieved items carries the key), when
    `shared_others` of the `others` items do."""
    if others <= 0 or shared_others <= 0:
        return 0.0
    k = min(k, others)
    return 1 - comb(others - shared_others, k) / comb(others, k)


def growth(
    keys: list[str], sizes: Sequence[int] = (100, 200, 400, 800), draws: int = 30
) -> list[dict[str, Any]]:
    """Share of titles whose key is shared, and the commonest key's share, in random
    subsets of growing size (fixed seed). Sharing rises with corpus size because the
    key space is small: a trend to extrapolate from, not a forecast."""
    rng = random.Random(0)  # noqa: S311 - a reproducible sample, not security
    out = []
    for n in sizes:
        if n > len(keys):
            continue
        shared = top = 0.0
        for _ in range(draws):
            c = Counter(rng.sample(keys, n))
            shared += sum(v for v in c.values() if v > 1) / n
            top += c.most_common(1)[0][1] / n
        out.append(
            {
                "titles": n,
                "share_shared": round(shared / draws, 4),
                "commonest_key_share": round(top / draws, 4),
            }
        )
    return out


def measure(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    titles = sorted({r["title"] for r in records if r.get("title")})
    keyed = {t: keys_of(t) for t in titles}
    first = {t: ks[0] for t, ks in keyed.items() if ks}  # a title's own key
    counts = Counter(first.values())
    n = len(first)
    shared = [t for t, k in first.items() if counts[k] > 1]
    common = [t for t, k in first.items() if right_token(k) in COMMON_RIGHT]
    top = counts.most_common(20)

    # Title reach: a name with this key is accepted if k OTHER retrieved cases share it.
    mean1 = mean8 = 0.0
    for k in first.values():
        mean1 += reach(counts[k] - 1, n - 1, 1)
        mean8 += reach(counts[k] - 1, n - 1, 8)

    # Text reach: the verifier also accepts a key found in the TEXT of any retrieved
    # passage, so count the records whose text contains each key.
    bodies = [f" {_norm_case_name(r['text'])} " for r in records if r.get("text")]
    nb = len(bodies)
    in_text = {k: sum(1 for b in bodies if f" {k} " in b) for k in counts}
    p8 = {k: reach(in_text[k], nb, 8) for k in counts}
    mean_p8 = sum(p8[k] for k in first.values()) / n if n else 0.0
    best_key, best_n = top[0] if top else ("", 0)
    return {
        "records": len(records),
        "distinct_titles": len(titles),
        "titles_with_a_key": n,
        "titles_without_a_key": len(titles) - n,
        "distinct_keys": len(counts),
        "keys_per_title": round(len(counts) / n, 4) if n else 0.0,
        "top20_keys": [
            {
                "key": k,
                "titles": c,
                "share_of_titles": _share(c, n),
                "records_whose_text_contains_it": in_text[k],
                "p_accepted_if_8_random_records_retrieved": round(p8[k], 4),
            }
            for k, c in top
        ],
        "share_of_titles_whose_key_is_shared": _share(len(shared), n),
        "share_of_titles_with_right_token_in": {
            "tokens": list(COMMON_RIGHT),
            "share": _share(len(common), n),
            "by_token": {
                t: _share(sum(1 for k in first.values() if right_token(k) == t), n)
                for t in COMMON_RIGHT
            },
        },
        "top_key_alone": {
            "key": best_key,
            "titles": best_n,
            "share_of_titles": _share(best_n, n),
        },
        "growth_with_corpus_size": growth(list(first.values())),
        "text_reach": {
            "records_with_text": nb,
            "mean_p_accepted_if_8_random_records_retrieved": round(mean_p8, 4),
            "note": "a name carrying its own title's key; the verifier accepts a key "
            "found in the title OR the text of any retrieved passage",
        },
        "title_reach_if_k_random_other_cases_retrieved": {
            "k=1": round(mean1 / n, 4) if n else 0.0,
            "k=8": round(mean8 / n, 4) if n else 0.0,
            "note": "random retrieval; real retrieval is topical, so approximate",
        },
    }


def _as_sentence(title: str) -> str:
    """A title written the way an answer would name it."""
    t = re.sub(r"\s+(?:versus|vs\.?)\s+", " v. ", title.strip().rstrip("."), flags=re.I)
    return f"The leading authority is {t.title()}."


def confirm_with_the_verifier(
    titles: Iterable[str], limit: int = 120
) -> dict[str, Any]:
    """Ask the REAL check whether naming B is accepted when only A was retrieved.
    Pairs with equal keys should be accepted, pairs with different keys should not; if
    not, `keys_of` is not the verifier's key and the numbers above are wrong."""
    ks = {t: keys_of(t) for t in sorted(set(titles))}
    ks = {t: k[0] for t, k in ks.items() if k}
    names = list(ks)[:limit]
    same = [0, 0]  # accepted, total (A != B, same key)
    diff = [0, 0]
    for a in names:
        passage = [Passage("x", "", source_id="S1", title=a)]
        for b in names:
            if a == b:
                continue
            accepted = not _unretrieved_authority(_as_sentence(b), passage)
            bucket = same if ks[a] == ks[b] else diff
            bucket[0] += accepted
            bucket[1] += 1
    return {
        "titles_checked": len(names),
        "pairs_with_the_same_key": {"accepted": same[0], "of": same[1]},
        "pairs_with_different_keys": {"accepted": diff[0], "of": diff[1]},
    }


# --- 4. Command line -----------------------------------------------------------------


def render(m: dict[str, Any], c: dict[str, Any]) -> str:
    out = [
        f"records {m['records']}, distinct titles {m['distinct_titles']} "
        f"({m['titles_without_a_key']} with no 'v', e.g. Acts), distinct keys "
        f"{m['distinct_keys']} over {m['titles_with_a_key']} keyed titles",
        "",
        f"{'key':<30}{'titles':>8}{'% titles':>10}{'in text of':>12}"
        f"{'P(accept|8)':>13}",
    ]
    for r in m["top20_keys"]:
        out.append(
            f"{r['key']:<30}{r['titles']:>8}{r['share_of_titles']:>10.1%}"
            f"{r['records_whose_text_contains_it']:>12}"
            f"{r['p_accepted_if_8_random_records_retrieved']:>13.1%}"
        )
    rt = m["share_of_titles_with_right_token_in"]
    e = m["title_reach_if_k_random_other_cases_retrieved"]
    tr = m["text_reach"]
    same, diff = c["pairs_with_the_same_key"], c["pairs_with_different_keys"]
    best = m["top20_keys"][0]["p_accepted_if_8_random_records_retrieved"]
    out += [
        "",
        "titles whose key is shared by at least one other title: "
        f"{m['share_of_titles_whose_key_is_shared']:.1%}",
        "titles whose right-hand token is union/state/commissioner: "
        f"{rt['share']:.1%} ("
        + ", ".join(f"{k} {v:.1%}" for k, v in rt["by_token"].items())
        + ")",
        f"the single commonest key '{m['top_key_alone']['key']}' is carried by "
        f"{m['top_key_alone']['share_of_titles']:.1%} of titles",
        "growth with corpus size (random subsets): "
        + "; ".join(
            f"{g['titles']} titles {g['share_shared']:.0%} shared, commonest "
            f"{g['commonest_key_share']:.1%}"
            for g in m["growth_with_corpus_size"]
        ),
        f"accepted via other cases' TITLES, k=1 {e['k=1']:.1%}, k=8 {e['k=8']:.1%}",
        "accepted via passage TEXT, name with its own title's key, 8 random records: "
        f"{tr['mean_p_accepted_if_8_random_records_retrieved']:.1%} "
        f"(commonest key {best:.1%})",
        "",
        f"verifier cross-check ({c['titles_checked']} titles): same key accepted "
        f"{same['accepted']}/{same['of']}, different key accepted "
        f"{diff['accepted']}/{diff['of']}",
    ]
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--titles", type=Path, help="records with a `title` field")
    ap.add_argument("--out", type=Path, help="write the JSON result here")
    a = ap.parse_args(argv)
    records = read_records(a.titles) if a.titles else default_records()
    m = measure(records)
    c = confirm_with_the_verifier([r["title"] for r in records if r.get("title")])
    m["source"] = str(a.titles) if a.titles else "practice fixtures (a sample)"
    print(render(m, c))
    print(f"source: {m['source']}")
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        doc = {"measure": m, "verifier_check": c}
        a.out.write_text(json.dumps(doc, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
