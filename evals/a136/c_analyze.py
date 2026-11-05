import collections
import json
import sys

import numpy as np

from core import court_id
from evals.a136.paths import REPO, RESULTS

R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else RESULTS / "c_results.json"))
rng = np.random.default_rng(13)
F = dict(json.load(open(RESULTS / "court_facets.json"))["legal_corpus_v2"])
w = collections.Counter()
reg = json.load(open(REPO / "core" / "court_models.json"))["collections"][
    "legal_corpus_v2"
]["courts"]
for label, n in F.items():
    c = court_id.court_for_label(label)
    if c:
        codes = [x for x in c.codes if x in reg]
        for x in codes:
            w[x] += n / len(codes)
tot = sum(w.values())
W = {c: w[c] / tot for c in reg}


def est(rows, mode, k, weighted, B=3000):
    by = collections.defaultdict(list)
    for r in rows:
        by[r["id"]].append(
            (r["code"], int(r[f"L_{mode}"] <= k) - int(r[f"a_{mode}"] <= k))
        )
    keys = list(by)
    codes = {t: by[t][0][0] for t in keys}

    def stat(sel):
        if not weighted:
            return np.mean([d for t in sel for _, d in by[t]]) * 100
        per = collections.defaultdict(list)
        for t in sel:
            per[codes[t]] += [d for _, d in by[t]]
        return (
            sum(W[c] * np.mean(v) for c, v in per.items())
            / sum(W[c] for c in per)
            * 100
        )

    pt = stat(keys)
    bs = [
        stat([keys[i] for i in rng.integers(0, len(keys), len(keys))]) for _ in range(B)
    ]
    lo, hi = np.percentile(bs, [2.5, 97.5])
    g = sum(1 for r in rows if r[f"L_{mode}"] <= k and not r[f"a_{mode}"] <= k)
    lost = sum(1 for r in rows if r[f"a_{mode}"] <= k and not r[f"L_{mode}"] <= k)
    base = np.mean([r[f"a_{mode}"] <= k for r in rows]) * 100
    return pt, lo, hi, g, lost, base


print("targets", len({r["id"] for r in R}), "queries", len(R))
for style in ("sentence", "paraphrase", None):
    rows = [r for r in R if style is None or r["style"] == style]
    print(
        f"\n== {style or 'BOTH STYLES'}: {len(rows)} queries, {len({r['id'] for r in rows})} targets;  single LARGE minus single voyage-4"
    )
    for wtd in (False, True):
        for mode, k in (("dense", 10), ("hybrid", 10), ("dense", 50), ("hybrid", 50)):
            pt, lo, hi, g, lost, base = est(rows, mode, k, wtd)
            v = "" if lo <= 0 <= hi else ("  CLEAR +" if pt > 0 else "  CLEAR -")
            print(
                f"{'vol-wtd' if wtd else 'equal  '} {mode:6}@{k:<3} base {base:5.1f}  net {pt:+5.1f} [{lo:+5.1f},{hi:+5.1f}] gained/lost {g}/{lost}{v}"
            )
print("\nBY the court's registered model (equal weight, both styles):")
for m in ("voyage-4", "voyage-4-lite", "voyage-4-large"):
    rows = [r for r in R if r["model"] == m]
    for mode, k in (("dense", 10), ("hybrid", 10)):
        pt, lo, hi, g, lost, base = est(rows, mode, k, False)
        print(
            f"  {m:15} {mode}@{k}: {pt:+5.1f} [{lo:+5.1f},{hi:+5.1f}]  ({len({r['code'] for r in rows})} codes)"
        )
