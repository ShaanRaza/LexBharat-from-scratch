"""Voyage tokens of the whole-missing English chunks, counted locally and for free (A141 cost picture).

`scan/missing_set.py` measured how many chunks and characters the missing set holds. This turns characters into the thing
Voyage bills, tokens, by running the same tokenizer Voyage publishes (`voyageai/voyage-4` on the Hugging Face hub, the one
`voyageai.Client.count_tokens` uses) over the parquet `text` of every chunk. No Voyage call, no key, no cost; the only
network use is downloading the tokenizer file once.

Billed tokens are the local count minus one special token per text (data/voyage_token_count.py). That offset is not assumed: `validate` checks it against
two runs whose billed tokens are in the token ledger (the 2,000-chunk model comparison and the 10,112-chunk INSC (A129)
embed on parquet text), and `run` refuses to start if either is off.

  python -m scan.missing_tokens validate
  python -m scan.missing_tokens run        # checkpoints one file at a time; safe to stop and re-run

Needs `tokenizers` and `pyarrow` (the repo `dev` extra has neither pyarrow nor voyageai; see evals/a141/README.md).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from data import voyage_token_count as vtc
from scan import coverage_gap as g
from scan import missing_set as ms

LEDGER = Path.home() / "qdrant-kanoon" / "kerala_fix" / "token_ledger.jsonl"


def tokenizer():
    return vtc._tokenizer()


def count(tok, texts: list[str]) -> np.ndarray:
    """Billed tokens per text (the method and its two checks are in data/voyage_token_count.py)."""
    return np.array(vtc.billed_tokens(texts, tok), dtype=np.int32)


def ledger(prefix: str) -> int:
    return sum(
        r["tokens"]
        for r in map(json.loads, LEDGER.read_text().splitlines())
        if r["tag"].startswith(prefix)
    )


def read_text_tokens(tok, pf, rows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """tokens and decision year for the given parquet row positions (only the row groups that hold one are read)."""
    starts = np.cumsum(
        [0]
        + [pf.metadata.row_group(i).num_rows for i in range(pf.metadata.num_row_groups)]
    )
    which = np.searchsorted(starts, rows, side="right") - 1
    toks = np.zeros(len(rows), dtype=np.int32)
    year = np.zeros(len(rows), dtype=np.int16)
    for rg in np.unique(which):
        t = pf.read_row_group(int(rg), columns=["text", "year"])
        sel = np.flatnonzero(which == rg)
        pos = rows[sel] - starts[rg]
        texts = t.column("text").to_pylist()
        toks[sel] = count(tok, [texts[p] for p in pos])
        y = t.column("year").fill_null(0).to_numpy(zero_copy_only=False)
        year[sel] = y[pos]
    return toks, year


def validate(home: Path) -> dict:
    import pyarrow.parquet as pq

    tok = tokenizer()
    out: dict = {}
    # 1. the 2,000-chunk model comparison: billed tokens per model are in the ledger
    corpus = json.loads(
        (
            Path.home() / "qdrant-kanoon" / "a128_confirm" / "a141m_corpus.json"
        ).read_text()
    )
    n = int(count(tok, [r["text"] for r in corpus]).sum())
    billed = ledger("model-choice voyage-4 batch")
    out["model_comparison_2000_chunks"] = {
        "local": n,
        "billed": billed,
        "difference": n - billed,
    }
    # 2. the 10,112 INSC chunks A129 embedded, from the parquet text
    codes = json.loads((home / "parquet" / "codes.json").read_text())
    en = json.loads((home / "parquet" / "langs.json").read_text())["en"]
    q_ch, _ = ms.load_q(home)
    sc = codes.index("INSC")
    f = next(g.PARQUET_DIR.glob("in_supreme-court_judgments.parquet"))
    z = np.load(home / "parquet" / (f.stem + ".npz"))
    rows = np.flatnonzero(
        ~np.isin(z["chash"], q_ch) & (z["lang"] == en) & (z["code"] == sc)
    )
    toks, _ = read_text_tokens(tok, pq.ParquetFile(f), rows)
    billed = ledger("sc embed batch")
    out["supreme_court_a129"] = {
        "chunks": int(len(rows)),
        "local": int(toks.sum()),
        "billed": billed,
        "difference": int(toks.sum()) - billed,
    }
    return out


def main() -> None:
    import pyarrow.parquet as pq

    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["validate", "run"])
    ap.add_argument("--home", default=str(g.HOME_DEFAULT))
    a = ap.parse_args()
    home = Path(a.home)
    v = validate(home)
    print(json.dumps(v, indent=1))
    ok = all(abs(x["difference"]) <= max(50, 0.0005 * x["billed"]) for x in v.values())
    if a.stage == "validate":
        return
    if not ok:
        raise SystemExit(
            "the local count does not reproduce the billed tokens; not running"
        )
    codes = json.loads((home / "parquet" / "codes.json").read_text())
    en = json.loads((home / "parquet" / "langs.json").read_text())["en"]
    q_ch, q_ca = ms.load_q(home)
    tok = tokenizer()
    ck = home / "missing_tokens"
    ck.mkdir(exist_ok=True)
    t0 = time.time()
    for f in sorted(g.PARQUET_DIR.glob("in_*_judgments.parquet")):
        dst = ck / (f.stem + ".npz")
        if dst.exists():
            continue
        z = np.load(home / "parquet" / (f.stem + ".npz"))
        ch, ca, co, lg = z["chash"], z["cash"], z["code"], z["lang"]
        cand = np.flatnonzero(~np.isin(ch, q_ch) & (lg == en) & ~np.isin(ca, q_ca))
        if len(cand):
            toks, year = read_text_tokens(tok, pq.ParquetFile(f), cand)
        else:
            toks, year = np.zeros(0, np.int32), np.zeros(0, np.int16)
        np.savez(
            dst, chash=ch[cand], cash=ca[cand], code=co[cand], tokens=toks, year=year
        )
        print(
            f"{f.name}: {len(cand):,} chunks, {int(toks.sum()):,} tokens ({time.time() - t0:.0f}s)",
            flush=True,
        )
    parts = [np.load(p) for p in sorted(ck.glob("in_*.npz"))]
    cat = {
        k: np.concatenate([p[k] for p in parts])
        for k in ("chash", "cash", "code", "tokens", "year")
    }
    agg = ms.aggregate(
        cat["chash"], cat["cash"], cat["code"], cat["tokens"], cat["year"]
    )
    named = {
        codes[k]: {
            **{kk: vv for kk, vv in v.items() if kk in ("cases", "chunks", "by_year")},
            "tokens": v["chars"],
        }
        for k, v in agg.items()
    }
    expect = json.loads((home / "missing_set.json").read_text())[
        "integrity_vs_section_19"
    ]
    cases = sum(v["cases"] for v in named.values())
    chunks = sum(v["chunks"] for v in named.values())
    if [cases, chunks] != [expect["cases"][1], expect["chunks"][1]]:
        raise SystemExit(
            f"INTEGRITY FAILED: {cases:,} cases / {chunks:,} chunks vs section 19"
        )
    (home / "missing_tokens.json").write_text(
        json.dumps(
            {
                "validation": v,
                "codes": named,
                "total_tokens": sum(v["tokens"] for v in named.values()),
            },
            indent=1,
        )
    )
    print(
        f"wrote missing_tokens.json; total {sum(v['tokens'] for v in named.values()):,} tokens ({time.time() - t0:.0f}s)"
    )


if __name__ == "__main__":
    main()
