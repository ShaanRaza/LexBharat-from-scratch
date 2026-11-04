"""Price any Voyage embedding job EXACTLY before spending on it (A141; docs/COSTS.md "Exact token counts").

Voyage bills by token. Its tokenizer is published (`voyageai/<model>` on the Hugging Face hub, the one
`voyageai.Client.count_tokens` uses), so the number of tokens a job will bill can be counted on this laptop, for free,
before a single request is made. Billed tokens are the local count MINUS ONE special token per text.

That offset and the whole method were checked against two real billed runs from the token ledger, with ZERO difference:
  * the 2,000-chunk document-model comparison: 1,864,904 local = 1,864,904 billed, under each of the three models;
  * the 10,112 Supreme Court chunks embedded for A129, counted from the parquet text: 9,546,375 local = 9,546,375 billed.
`scan/missing_tokens.py` re-runs both checks before it counts anything.

Not verified: the rerank models, models outside the voyage-4 family, and whether the Batch API bills the same token count
as the standard endpoint (it should; the discount is on price, not tokens). A text over the model's context length is
truncated by Voyage; this counts it untruncated, so such a text would be over-counted here.

Pipeline step 5 (Search) data preparation. No Voyage call, no key, no spend: the only network use is downloading the
tokenizer file once. Needs the `tokenizers` package (installed with `fastembed`, which the `dev` extra has).

  python -m data.voyage_token_count chunks.jsonl            # one JSON object per line, text in the "text" field
  python -m data.voyage_token_count a.txt b.txt --field text
"""

from __future__ import annotations

import argparse
import functools
import json
from collections.abc import Iterable
from pathlib import Path

SPECIAL_PER_TEXT = 1
# USD per 1M tokens, standard endpoint. Vendor pricing page, fetched 4 Nov 2026 (DATA-GAPS section 13 carries the same figures).
PRICE_PER_MTOK = {"voyage-4-lite": 0.02, "voyage-4": 0.06, "voyage-4-large": 0.12}
# The Batch API is 33% cheaper (vendor batch page, fetched 4 Nov 2026). Free tokens are not stated to apply to batch.
BATCH_DISCOUNT = 0.33
# One tokenizer serves the whole voyage-4 family (the ledger shows identical counts for all three models on the same texts).
TOKENIZER_MODEL = "voyage-4"


@functools.cache
def _tokenizer(model: str = TOKENIZER_MODEL):
    from tokenizers import Tokenizer

    t = Tokenizer.from_pretrained(f"voyageai/{model}")
    t.no_truncation()
    return t


def billed_tokens(texts: Iterable[str], tokenizer=None) -> list[int]:
    """Tokens Voyage will bill for each text (document or query: the count does not depend on input_type)."""
    tok = tokenizer or _tokenizer()
    texts = list(texts)
    out: list[int] = []
    for i in range(0, len(texts), 1000):
        out += [
            len(e.ids) - SPECIAL_PER_TEXT for e in tok.encode_batch(texts[i : i + 1000])
        ]
    return out


def price_usd(tokens: int, model: str, batch: bool = False) -> float:
    """List price of `tokens` under `model`. Before the free allowance, which is not applied here."""
    if model not in PRICE_PER_MTOK:
        raise ValueError(
            f"no price recorded for {model!r}; known: {sorted(PRICE_PER_MTOK)}"
        )
    p = PRICE_PER_MTOK[model] * ((1 - BATCH_DISCOUNT) if batch else 1.0)
    return tokens / 1e6 * p


def _texts_from(path: Path, field: str) -> list[str]:
    if path.suffix == ".jsonl":
        return [
            json.loads(line)[field]
            for line in path.read_text().splitlines()
            if line.strip()
        ]
    if path.suffix == ".json":
        data = json.loads(path.read_text())
        return [d[field] if isinstance(d, dict) else d for d in data]
    return [path.read_text()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--field", default="text")
    a = ap.parse_args()
    texts = [t for f in a.files for t in _texts_from(f, a.field)]
    n = sum(billed_tokens(texts))
    print(
        f"{len(texts):,} texts, {n:,} billed tokens ({n / max(len(texts), 1):,.0f} per text)"
    )
    for m in PRICE_PER_MTOK:
        print(
            f"  {m:15} standard ${price_usd(n, m):>10,.4f}   batch ${price_usd(n, m, batch=True):>10,.4f}"
        )


if __name__ == "__main__":
    main()
