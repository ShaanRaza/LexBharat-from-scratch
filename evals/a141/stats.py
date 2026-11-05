"""Recall and the cluster bootstrap used by every A141 comparison (numpy only, so any environment can import it)."""

from __future__ import annotations

import numpy as np

K_LIST = (10, 50)
BOOT = 3000


def recall(rows, cond, k):
    return float(np.mean([r[cond] <= k for r in rows]) * 100)


def diff_ci(rows, a, b, k, rng):
    """b minus a at rank k, cluster bootstrap over targets (a target's queries move together)."""
    by: dict = {}
    for r in rows:
        by.setdefault(r["id"], []).append(int(r[b] <= k) - int(r[a] <= k))
    keys = list(by)
    pt = float(np.mean([d for t in keys for d in by[t]]) * 100)
    bs = [
        np.mean(
            [
                d
                for t in (keys[j] for j in rng.integers(0, len(keys), len(keys)))
                for d in by[t]
            ]
        )
        * 100
        for _ in range(BOOT)
    ]
    lo, hi = np.percentile(bs, [2.5, 97.5])
    gained = sum(1 for r in rows if r[b] <= k < r[a])
    lost = sum(1 for r in rows if r[a] <= k and not r[b] <= k)
    return pt, float(lo), float(hi), gained, lost
