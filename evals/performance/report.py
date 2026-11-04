"""Turn evals/performance/measure.py output into the CLAUDE.md section 10 table (measurement only).

Every figure is a percentile of the recorded per-question or per-call times: p50 and p95, never an average. A target
PASSES when its p95 is under the target, because the tail is what a user feels as slow. Where a target fails, the report
says which step takes the time (by p50) and what that step spent inside vendor calls (Gemini, Voyage, Qdrant) against
our own code, so the cause is a measured split and not a guess.

  python -m evals.performance.report --in ~/qdrant-kanoon/performance/timing.jsonl [--write-metrics docs/METRICS.md]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from evals.performance.timing import p50_p95

TARGETS = {
    "first_word": 3.0,
    "full_answer": 20.0,
    "search_stage": 0.8,
    "decision": 0.8,
    "lookup": 0.5,
}
STEP_ORDER = [
    ("remember", "1 Remember"),
    ("rewrite", "2 Rewrite"),
    ("decide_embed", "3 Decide (scope check, in parallel with the query embedding)"),
    ("cache", "4 Cache (in-memory stand-in)"),
    ("search", "5 Search"),
    ("rerank", "6 Re-rank"),
    ("gate", "7 Gate"),
    ("answer", "8 Answer"),
    ("verify", "9 Verify"),
    ("show", "10 Show (after step 11, as the API bridge runs it)"),
    ("save", "11 Save (in-memory stand-in)"),
]
BEGIN, END = "<!-- latency:begin -->", "<!-- latency:end -->"


def load_rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def step3(row: dict) -> float | None:
    """Step 3 runs the scope decision and the query embedding in parallel: its time is the longer of the two."""
    d, e = row["steps"].get("decide"), row["steps"].get("embed_query")
    return (
        max(x for x in (d, e) if x is not None)
        if (d is not None or e is not None)
        else None
    )


def step_values(rows: list[dict]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {k: [] for k, _ in STEP_ORDER}
    for r in rows:
        for k, _ in STEP_ORDER:
            v = step3(r) if k == "decide_embed" else r["steps"].get(k)
            if v is not None:
                out[k].append(v)
    return out


def call_values(rows: list[dict], kind: str) -> list[float]:
    return [v for r in rows for v in r["calls"].get(kind, [])]


def vendor_split(rows: list[dict], step: str) -> dict[str, float]:
    """The median seconds a step spent inside each vendor, over the questions in which it ran."""
    key = "decide" if step == "decide_embed" else step
    shares: dict[str, list[float]] = {}
    for r in rows:
        if key not in r["steps"] and step != "decide_embed":
            continue
        for vendor, sec in r["vendor_in_step"].get(key, {}).items():
            shares.setdefault(vendor, []).append(sec)
    return {k: p50_p95(v)[0] or 0.0 for k, v in shares.items()}


def fmt(x: float | None, unit: str = "s") -> str:
    if x is None:
        return "-"
    return f"{x * 1000:,.0f} ms" if unit == "ms" or x < 1.0 else f"{x:,.1f} s"


def verdict(p95: float | None, target: float) -> str:
    return "-" if p95 is None else ("PASS" if p95 < target else "**FAIL**")


def build(rows: list[dict]) -> dict:
    answered = [r for r in rows if r["outcome"] == "answered"]
    both = [r for r in rows if "search" in r["steps"] and "rerank" in r["steps"]]
    lookup_rows = [
        r
        for r in rows
        if r.get("scope") in ("act+section", "act") and "search" in r["steps"]
    ]
    targets = []

    def add(name, target, values, n_note, why=""):
        p50, p95 = p50_p95(values)
        targets.append(
            {
                "measure": name,
                "target": target,
                "p50": p50,
                "p95": p95,
                "n": len(values),
                "note": n_note,
                "result": verdict(p95, target),
                "why": why,
            }
        )

    add(
        "First word of a research answer",
        TARGETS["first_word"],
        [r["first_word_seconds"] for r in answered],
        "answered questions",
    )
    add(
        "Full research answer",
        TARGETS["full_answer"],
        [r["full_answer_seconds"] for r in answered],
        "answered questions",
    )
    add(
        "Search stage (search + re-rank)",
        TARGETS["search_stage"],
        [r["steps"]["search"] + r["steps"]["rerank"] for r in both],
        "every question that reached re-rank",
    )
    for kind, label in (
        ("decide", "scope decision"),
        ("rate_passage", "gate rating (one passage)"),
        ("claim_support", "claim check (verifier check 4)"),
    ):
        add(
            f"Each Gemini decision: {label}",
            TARGETS["decision"],
            call_values(rows, f"decision:{kind}"),
            "every call",
            "",
        )
    add(
        "Act / section lookup (search step, exact or Act-scoped)",
        TARGETS["lookup"],
        [r["steps"]["search"] for r in lookup_rows],
        "questions whose search ran an Act-scoped lookup",
    )
    return {"targets": targets, "answered": len(answered), "rows": len(rows)}


def _split_text(rows: list[dict], step: str) -> str:
    split = vendor_split(rows, step)
    return (
        ", ".join(
            f"{v} {fmt(s)}" for v, s in sorted(split.items(), key=lambda t: -t[1])
        )
        or "no vendor call"
    )


def explain(rows: list[dict], measure: str) -> str:
    """For a failing measure: where its own time goes, as measured (never a guess)."""
    names = dict(STEP_ORDER)
    if measure.startswith(("First word", "Full research")):
        steps = step_values(rows)
        ranked = sorted(
            ((p50_p95(v)[0] or 0.0, k) for k, v in steps.items() if v), reverse=True
        )[:3]
        parts = [
            f"{names[k].split(' (')[0]} p50 {fmt(p50)} (median inside: {_split_text(rows, k)})"
            for p50, k in ranked
        ]
        answered = [r for r in rows if r["outcome"] == "answered"]
        rest = [
            r["first_word_seconds"] - r["steps"].get("verify", 0.0) for r in answered
        ]
        p50, p95 = p50_p95(rest)
        parts.append(
            f"with step 9 taken out the same questions would be p50 {fmt(p50)}, p95 {fmt(p95)}"
        )
        return "; ".join(parts)
    if measure.startswith("Search stage"):
        s, r = (
            p50_p95(step_values(rows)["search"]),
            p50_p95(step_values(rows)["rerank"]),
        )
        return (
            f"search (Qdrant) p50 {fmt(s[0])}, p95 {fmt(s[1])}; re-rank (Voyage) p50 {fmt(r[0])}, "
            f"p95 {fmt(r[1])}"
        )
    if measure.startswith("Each Gemini decision"):
        kind = {"scope": "decide", "gate": "rate_passage", "claim": "claim_support"}[
            "scope" if "scope" in measure else "gate" if "gate" in measure else "claim"
        ]
        d = p50_p95(call_values(rows, f"decision:{kind}"))
        g = p50_p95(call_values(rows, f"gemini:{kind}"))
        if kind == "claim_support":
            return (
                f"the whole call p50 {fmt(d[0])}, p95 {fmt(d[1])}; claim_support is not timed "
                "separately inside the API call, so the call time is the Gemini round trip plus our parsing"
            )
        return (
            f"the whole decision p50 {fmt(d[0])}, p95 {fmt(d[1])}, of which the Gemini API call "
            f"p50 {fmt(g[0])}, p95 {fmt(g[1])} (our own code adds the difference)"
        )
    return ""


def render(rows: list[dict], summary: dict, when: str, conditions: str) -> str:
    rep = build(rows)
    L = [f"## Latency against the CLAUDE.md section 10 targets (measured {when})", ""]
    L.append(conditions.strip())
    L.append("")
    L.append(
        "A target PASSES when its p95 is under it. p50 and p95 are percentiles of the recorded times, never averages."
    )
    L.append("")
    L.append("| Measure | Target | p50 | p95 | n | Result |")
    L.append("|---|---|---:|---:|---:|---|")
    for t in rep["targets"]:
        unit = "ms" if t["target"] < 1.0 else "s"
        tgt = (
            f"under {t['target'] * 1000:,.0f} ms"
            if unit == "ms"
            else f"under {t['target']:.0f} s"
        )
        L.append(
            f"| {t['measure']} | {tgt} | {fmt(t['p50'], unit)} | {fmt(t['p95'], unit)} | {t['n']} | {t['result']} |"
        )
    L.append("")
    L.append("### Per step (the 11 pipeline steps)")
    L.append("")
    L.append("| Step | p50 | p95 | n | Median spent inside vendor calls |")
    L.append("|---|---:|---:|---:|---|")
    steps = step_values(rows)
    for k, label in STEP_ORDER:
        p50, p95 = p50_p95(steps[k])
        split = vendor_split(rows, k)
        inside = (
            ", ".join(
                f"{v} {fmt(s)}" for v, s in sorted(split.items(), key=lambda t: -t[1])
            )
            or "none (our own code)"
        )
        L.append(f"| {label} | {fmt(p50)} | {fmt(p95)} | {len(steps[k])} | {inside} |")
    L.append("")
    fails = [t for t in rep["targets"] if t["result"] == "**FAIL**"]
    if fails:
        L.append("### Where the time goes, for each failure")
        L.append("")
        for t in fails:
            L.append(
                f"- **{t['measure']}** (p95 {fmt(t['p95'])} against {fmt(t['target'])}): "
                + explain(rows, t["measure"])
                + "."
            )
        L.append("")
    L.append("### Other measured calls (for reading the table, not targets)")
    L.append("")
    L.append("| Call | p50 | p95 | n |")
    L.append("|---|---:|---:|---:|")
    kinds = sorted({k for r in rows for k in r["calls"]})
    for kind in kinds:
        v = call_values(rows, kind)
        p50, p95 = p50_p95(v)
        L.append(f"| {kind} | {fmt(p50)} | {fmt(p95)} | {len(v)} |")
    L.append("")
    return "\n".join(L)


def write_metrics(path: Path, block: str) -> None:
    text = path.read_text()
    new = f"{BEGIN}\n{block}\n{END}"
    if BEGIN in text:
        text = re.sub(
            re.escape(BEGIN) + r".*?" + re.escape(END), lambda _m: new, text, flags=re.S
        )
    else:
        text = text.rstrip("\n") + "\n\n" + new + "\n"
    path.write_text(text)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--in", dest="inp", type=Path, required=True)
    ap.add_argument("--summary", type=Path)
    ap.add_argument("--when", default="")
    ap.add_argument("--conditions", default="")
    ap.add_argument("--write-metrics", type=Path)
    a = ap.parse_args()
    rows = load_rows(a.inp)
    summary = json.loads(
        (a.summary or a.inp.with_name(a.inp.stem + "_summary.json")).read_text()
    )
    block = render(rows, summary, a.when, a.conditions)
    if a.write_metrics:
        write_metrics(a.write_metrics, block)
        print(f"wrote the latency block into {a.write_metrics}")
    else:
        print(block)


if __name__ == "__main__":
    main()
