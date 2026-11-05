"""What would a stricter case-name rule cost? A measurement (A116, for A113).

A115 measured how often the current two-token key lets a fabricated name through.
This measures the other half: how many LEGITIMATE citations a stricter comparison
would strip. Nothing in core/ changes; rule a below IS the real verifier
(`_unretrieved_authority`); the others are candidates implemented here.

Rules, each answering "is this written case name among the retrieved passages?":
  a   the verifier as it stands (since A117 this IS rule f, integrated: the A116 table
      row "a" described the verifier before A117). The real function, asked about the
      name written two
      ways (natural: "Smith & Ors. v. State of X"; Title Case: "Smith And Ors. V.
      State Of X"), because its name-shape test reads them differently.
  b   the full normalised name must appear, as a contiguous run, in a retrieved title
      or in the text of a retrieved passage.
  c   order-aware containment: the share of the written name's words that match, in
      order, inside ONE retrieved case name (a title, or a "... v ..." span in a
      passage's text), accepted at or above a threshold. Several thresholds.
  c'  the same without order (a bag of words), at 1.0: shows why order matters.
  d   c with character-tolerant word matching (a typo, an OCR slip, Co./Company).
  e   c at 1.0 and the name must contain a word that is not generic.
  f   d at 1.0 and the name must contain a word that is not generic.
"Generic" = a word in at least 1% of case titles ("state", "union", "ltd", "singh"),
derived from the titles, not typed.

Two kinds of pair are scored.
  LEGITIMATE   a real title, and the ways a model plausibly writes it: drop "M/s",
               drop "& Ors.", drop "& Anr.", surname only (first and last word of the
               left party), "Co." written "Company", a one-letter slip, and first
               party only. The cited case IS retrieved and is the only passage handed
               over (the least generous case). A rejection is a FALSE POSITIVE: a
               real citation stripped (visible; safe).
  FABRICATED   a name accepted although no such case was retrieved: a FALSE NEGATIVE
               (invisible; the failure the product exists to prevent). Four kinds:
                 invented     a made-up surname + a realistic suffix + the right-hand
                              party of a real title, with 8 random records retrieved.
                 unretrieved  a real corpus case, shortened as above, that was not
                              among the 8 random records retrieved (check 1's job).
                 swapped      a retrieved case written with its parties reversed.
                 generic      a "name" made only of the commonest title words.

INPUT: the practice fixtures (1,398 records, a SAMPLE). Fixed seed; same numbers each
run. LIMITS: the shortenings are my list, not observed model output; surname-only is a
heuristic on Indian names; a first-party-only name has no "v" and no rule looks at it;
retrieval here is random, not topical; the one-letter and Company variants reach the
rule with no passage text containing them (a pessimistic case, since a model usually
copies the spelling it was given); and rules d, e and f were designed AFTER seeing how
c failed, so their false-positive rows on the variants they fix are not independent
evidence. Tolerating a one-letter slip also accepts an invented name one letter from a
retrieved one; that is the same behaviour, not a separate test.

    .venv/bin/python -m evals.title_rules --out rules.json
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from adapters.qdrant import Hit
from core.contracts import Passage
from core.search import hit_to_passage
from core.verify import _norm_case_name, _unretrieved_authority
from evals.title_keys import default_records, read_records

SEED = 20261103
THRESHOLDS = (0.6, 0.7, 0.8, 0.9, 1.0)
VARIANTS = (
    "drop_ms",
    "drop_ors",
    "drop_anr",
    "surname_first",
    "surname_last",
    "first_party",
    "abbrev",
    "one_char",
)
DELETIONS = VARIANTS[
    :5
]  # pure deletions: the written name is a subsequence of the title
_CANON = {"company": "co", "limited": "ltd", "private": "pvt", "corporation": "corpn"}
_ABBREV = {"co": "company", "ltd": "limited", "pvt": "private", "corpn": "corporation"}
_FILLER = {
    "m", "s", "messrs", "ltd", "limited", "co", "company", "pvt", "private", "and",
    "ors", "anr", "others", "another", "dr", "shri", "smt", "mr", "mrs", "the", "etc",
}  # fmt: skip

# --- 1. A written name, as tokens ---------------------------------------------------


def split_title(title: str) -> tuple[list[str], list[str]] | None:
    """(left party, right party) as normalised tokens, or None if there is no "v"."""
    toks = _norm_case_name(title).split()
    if "v" not in toks:
        return None
    i = toks.index("v")
    left, right = toks[:i], toks[i + 1 :]
    return (left, right) if left and right else None


def _drop_phrase(toks: list[str], words: tuple[str, ...]) -> list[str]:
    """Remove "and <w>" or a bare <w> for each w in `words`."""
    out = list(toks)
    for w in words:
        out = [
            t
            for i, t in enumerate(out)
            if t != w and not (t == "and" and i + 1 < len(out) and out[i + 1] == w)
        ]
    return out


def shorten(left: list[str], right: list[str], how: str) -> list[str] | None:
    """The written name's tokens ("v" included), or None if this shortening changes
    nothing for this title (then it is not a shortening of it)."""
    full = left + ["v"] + right
    if how == "drop_ms":
        new = (
            (
                left[2:]
                if left[:2] == ["m", "s"]
                else left[1:]
                if left[0] == "messrs"
                else left
            )
            + ["v"]
            + right
        )
    elif how == "drop_ors":
        new = (
            _drop_phrase(left, ("ors", "others"))
            + ["v"]
            + _drop_phrase(right, ("ors", "others"))
        )
    elif how == "drop_anr":
        new = (
            _drop_phrase(left, ("anr", "another"))
            + ["v"]
            + _drop_phrase(right, ("anr", "another"))
        )
    elif how in ("surname_first", "surname_last"):
        core = [t for t in left if t not in _FILLER and len(t) > 1]
        if not core:
            return None
        new = [core[0] if how == "surname_first" else core[-1], "v"] + right
    elif how == "abbrev":  # "Co." written "Company", "Ltd." written "Limited"
        new = (
            [_ABBREV.get(t, t) for t in left]
            + ["v"]
            + [_ABBREV.get(t, t) for t in right]
        )
    elif how == "one_char":  # one slip in the longest word (a typo, or an OCR error)
        new = list(full)
        i = max(range(len(new)), key=lambda k: len(new[k]))
        if len(new[i]) < 5:
            return None
        new[i] = new[i][: len(new[i]) // 2] + "x" + new[i][len(new[i]) // 2 + 1 :]
    elif how == "first_party":
        new = list(left)  # no "v": the form most likely to slip past any rule
    else:
        raise ValueError(how)
    return None if new == full or not new or new[0] == "v" or new[-1] == "v" else new


_SMALL = {"of", "the", "for", "in", "on", "to", "by"}
_DOTTED = {"ors": "Ors.", "anr": "Anr.", "ltd": "Ltd.", "co": "Co.", "pvt": "Pvt."}


def written(tokens: Sequence[str], style: str = "natural") -> str:
    """The tokens as an answer would write them. "natural": "&" before Ors./Anr./Co.,
    small words lowercase, "M/s", dotted abbreviations ("Smith & Ors. v. State of X").
    "titlecase": every word capitalised ("Smith And Ors. V. State Of X"). The verifier's
    name-shape test reads the two differently, so rule a is reported for both."""
    if style == "titlecase":
        return " ".join("v." if t == "v" else t.capitalize() for t in tokens)
    out: list[str] = []
    i = 0
    while i < len(tokens):
        t, nxt = tokens[i], tokens[i + 1] if i + 1 < len(tokens) else ""
        if t == "v":
            out.append("v.")
        elif t == "m" and nxt == "s":
            out.append("M/s")
            i += 1
        elif t == "and":
            out.append("&" if nxt in ("ors", "anr", "co", "company") else "and")
        elif t in _SMALL and out:
            out.append(t)
        elif t in _DOTTED:
            out.append(_DOTTED[t])
        else:
            out.append(t.capitalize())
        i += 1
    return " ".join(out)


def as_sentence(tokens: Sequence[str], style: str = "natural") -> str:
    return f"The leading authority is {written(tokens, style)}."


# --- 2. The retrieved set -----------------------------------------------------------


@dataclass(frozen=True)
class Rec:
    passage: Passage
    haystack: str  # normalised title + text, space padded
    names: tuple[
        tuple[str, ...], ...
    ]  # the case names in it: title + "... v ..." spans


def _spans(norm_text: str, width: int = 6) -> list[tuple[str, ...]]:
    toks = norm_text.split()
    return [
        tuple(toks[max(0, i - width) : i + 1 + width])
        for i, t in enumerate(toks)
        if t == "v" and 0 < i < len(toks) - 1
    ]


def build(records: Sequence[dict[str, Any]]) -> list[Rec]:
    out = []
    for r in records:
        hit = Hit(
            r["chunk_id"], r["text"], 0.0, {k: v for k, v in r.items() if k != "text"}
        )
        p = hit_to_passage(hit)
        title = _norm_case_name(p.title or "")
        body = _norm_case_name(p.text)
        names = [tuple(title.split())] if title else []
        out.append(Rec(p, f" {title} {body} ", tuple(names + _spans(body))))
    return out


# --- 3. The rules -------------------------------------------------------------------

Rule = Callable[[Sequence[str], Sequence[Rec]], bool]


def make_rule_a(style: str) -> Rule:
    def rule(tokens: Sequence[str], recs: Sequence[Rec]) -> bool:
        """The current rule: the real verifier, asked about this name."""
        sentence = as_sentence(tokens, style)
        return not _unretrieved_authority(sentence, [r.passage for r in recs])

    return rule


def rule_b(tokens: Sequence[str], recs: Sequence[Rec]) -> bool:
    return f" {' '.join(tokens)} " in "".join(r.haystack for r in recs)


def ordered_containment(name: Sequence[str], cand: Sequence[str]) -> float:
    m = SequenceMatcher(None, name, cand, autojunk=False)
    return sum(b.size for b in m.get_matching_blocks()) / len(name)


def _same_word(a: str, b: str) -> bool:
    """Equal, or (both 5+ letters) at least 80% alike letter by letter: absorbs a typo,
    an OCR slip or "Mulchand Agarwala" for "Agarwalla", not a different surname."""
    a, b = _CANON.get(a, a), _CANON.get(b, b)
    if a == b:
        return True
    return min(len(a), len(b)) >= 5 and SequenceMatcher(None, a, b).ratio() >= 0.8


def fuzzy_ordered_containment(name: Sequence[str], cand: Sequence[str]) -> float:
    """Longest in-order match (a subsequence, words compared with _same_word) as a share
    of the written name's words."""
    prev = [0] * (len(cand) + 1)
    for w in name:
        cur = [0]
        for j, c in enumerate(cand):
            cur.append(prev[j] + 1 if _same_word(w, c) else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1] / len(name)


def make_rule_d(theta: float) -> Rule:
    def rule(tokens: Sequence[str], recs: Sequence[Rec]) -> bool:
        return any(
            fuzzy_ordered_containment(tokens, cand) >= theta - 1e-9
            for r in recs
            for cand in r.names
        )

    return rule


def make_rule_c(theta: float, ordered: bool = True) -> Rule:
    def rule(tokens: Sequence[str], recs: Sequence[Rec]) -> bool:
        for r in recs:
            for cand in r.names:
                if ordered:
                    score = ordered_containment(tokens, cand)
                else:
                    score = len(set(tokens) & set(cand)) / len(set(tokens))
                if score >= theta - 1e-9:
                    return True
        return False

    return rule


def all_rules(generic: Sequence[str] = ()) -> dict[str, Rule]:
    rules: dict[str, Rule] = {
        "a  current, natural text": make_rule_a("natural"),
        "a  current, Title Case": make_rule_a("titlecase"),
        "b  full name": rule_b,
    }
    for t in THRESHOLDS:
        rules[f"c  ordered >= {t:.1f}"] = make_rule_c(t)
    rules["c' bag of words = 1.0"] = make_rule_c(1.0, ordered=False)
    for t in (0.9, 1.0):
        rules[f"d  ordered, fuzzy words >= {t:.1f}"] = make_rule_d(t)
    rules["e  c 1.0 + a distinctive word"] = make_rule_e(generic)
    rules["f  d 1.0 + a distinctive word"] = make_rule_e(generic, fuzzy=True)
    return rules


# --- 4. The two kinds of pair -------------------------------------------------------


def _vocab(recs: Sequence[Rec]) -> set[str]:
    return {t for r in recs for t in r.haystack.split()}


def generic_words(recs: Sequence[Rec], share: float = 0.01) -> list[str]:
    """Words in at least `share` of the case titles, most common first: the words that
    say little about WHICH case ("state", "union", "ltd", "ors"...). Derived from the
    titles, not typed."""
    df: Counter = Counter()
    seen = {
        r.passage.title
        for r in recs
        if r.passage.title and split_title(r.passage.title)
    }
    for t in seen:
        df.update(set(_norm_case_name(t).split()) - {"v"})
    # ties broken by the word, not by hash order, so every run gives the same list
    ranked = sorted(df, key=lambda w: (-df[w], w))
    return [w for w in ranked if df[w] / len(seen) >= share]


GENERIC_FILE = Path(__file__).parent.parent / "core" / "generic_title_words.json"


def write_generic_words(
    path: Path, records: Sequence[dict[str, Any]], source: str, share: float = 0.01
) -> dict[str, Any]:
    """Write the list core/verify.py reads (A117): words in at least `share` of the case
    titles. Derived from the data, never typed; regenerate it from the full title dump
    when there is one."""
    recs = build(records)
    titles = {
        r.passage.title
        for r in recs
        if r.passage.title and split_title(r.passage.title)
    }
    doc = {
        "share": share,
        "derived_from": source,
        "case_titles": len(titles),
        "how": "python -m evals.title_rules --write-generic "
        "core/generic_title_words.json [--titles dump]",
        "words": sorted(generic_words(recs, share)),
    }
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def make_rule_e(generic: Sequence[str], fuzzy: bool = False) -> Rule:
    """c at 1.0, and the written name must contain at least one word that is not generic
    (else "State v. Union" would pass whenever any retrieved name has those words)."""
    strict = make_rule_d(1.0) if fuzzy else make_rule_c(1.0)
    common = set(generic) | {"v"}

    def rule(tokens: Sequence[str], recs: Sequence[Rec]) -> bool:
        return any(t not in common for t in tokens) and strict(tokens, recs)

    return rule


def invented_surnames(vocab: set[str], n: int, rng: random.Random) -> list[str]:
    syl = ["bar", "kor", "vel", "mun", "dra", "zul", "pen", "tor", "fal", "quin", "mar",
           "jen", "wex", "lum", "nor", "ska", "bri", "gol", "hep", "yan"]  # fmt: skip
    out: list[str] = []
    while len(out) < n:
        w = "".join(rng.choice(syl) for _ in range(rng.choice((2, 3)))) + rng.choice(
            ("a", "an", "ex", "ov", "")
        )
        if w not in vocab and w not in out:
            out.append(w)
    return out


def legit(
    recs: Sequence[Rec], rules: dict[str, Rule], max_titles: int | None = None
) -> dict[str, Any]:
    by_title: dict[str, Rec] = {}
    for r in recs:
        if r.passage.title and split_title(r.passage.title):
            by_title.setdefault(r.passage.title, r)
    counts: dict[str, Counter] = {k: Counter() for k in rules}
    totals: Counter = Counter()
    for title, rec in list(by_title.items())[:max_titles]:
        left, right = split_title(title)  # type: ignore[misc]
        for how in VARIANTS:
            toks = shorten(left, right, how)
            if toks is None:
                continue
            totals[how] += 1
            for name, rule in rules.items():
                if how == "first_party":
                    # no "v": the verifier never looks at it, so it is accepted; a rule
                    # that does look would have to be a new feature (not measured here)
                    accepted = True if name.startswith("a ") else rule(toks, [rec])
                else:
                    accepted = rule(toks, [rec])
                counts[name][how] += not accepted  # a rejection is a false positive
    return {
        "titles": len(by_title),
        "pairs_by_variant": dict(totals),
        "rejected": {k: dict(v) for k, v in counts.items()},
    }


def fabricated(
    recs: Sequence[Rec],
    rules: dict[str, Rule],
    rng: random.Random,
    scale: float = 1.0,
) -> dict[str, Any]:
    vocab = _vocab(recs)
    n_names = max(1, int(200 * scale))
    titled = [(r, split_title(r.passage.title)) for r in recs if r.passage.title]
    titled = [(r, s) for r, s in titled if s]
    rights = [s[1] for _, s in titled]
    suffixes = [[], ["and", "ors"], ["and", "anr"], ["ltd"], ["m", "s", "&co"]]
    labels = ["X", "X & Ors.", "X & Anr.", "X Ltd.", "M/s X & Co."]
    scen: dict[str, list[tuple[list[str], list[Rec]]]] = {
        "invented": [],
        "unretrieved": [],
        "swapped": [],
        "generic": [],
    }
    top = generic_words(recs)[:12]

    pattern_of: list[str] = []
    for x in invented_surnames(vocab, n_names, rng):
        for k, suf in enumerate(suffixes):
            pattern_of.append(labels[k])
            left = (
                (["m", "s"] + [x, "and", "co"])
                if suf == ["m", "s", "&co"]
                else [x] + suf
            )
            scen["invented"].append(
                (left + ["v"] + rng.choice(rights), rng.sample(recs, 8))
            )

    for _ in range(int(1000 * scale)):
        rec, (left, right) = rng.choice(titled)
        toks = shorten(left, right, rng.choice(DELETIONS))
        if toks is None:
            continue
        pool = [r for r in recs if r.passage.title != rec.passage.title]
        scen["unretrieved"].append((toks, rng.sample(pool, 8)))

    for _ in range(300):  # a "name" made only of the commonest title words
        name = (
            rng.sample(top, rng.choice((1, 2)))
            + ["v"]
            + rng.sample(top, rng.choice((1, 2, 3)))
        )
        scen["generic"].append((name, rng.sample(recs, 8)))

    for _ in range(int(500 * scale)):
        rec, (left, right) = rng.choice(titled)
        pool = [r for r in recs if r is not rec]
        scen["swapped"].append((right + ["v"] + left, [rec, *rng.sample(pool, 7)]))

    out: dict[str, Any] = {
        "trials": {k: len(v) for k, v in scen.items()},
        "accepted": {},
        "invented_by_pattern": {},
        "pattern_trials": n_names,
    }
    for name, rule in rules.items():
        res = {k: [rule(t, rs) for t, rs in v] for k, v in scen.items()}
        out["accepted"][name] = {k: sum(v) for k, v in res.items()}
        out["invented_by_pattern"][name] = {
            lab: sum(a for a, p in zip(res["invented"], pattern_of) if p == lab)
            for lab in labels
        }
    return out


# --- 5. Report ----------------------------------------------------------------------


def measure(max_titles: int | None = None, scale: float = 1.0) -> dict[str, Any]:
    """The tests pass `max_titles` and `scale` for a small slice; the CLI runs all."""
    recs = build(default_records())
    rules = all_rules(generic_words(recs))
    rng = random.Random(SEED)  # noqa: S311 - a reproducible sample, not security
    return {
        "records": len(recs),
        "legitimate": legit(recs, rules, max_titles),
        "fabricated": fabricated(recs, rules, rng, scale),
    }


def pct(n: int, d: int) -> str:
    return f"{n / d:.1%}" if d else "-"


def render(m: dict[str, Any]) -> str:
    lg, fb = m["legitimate"], m["fabricated"]
    pairs = lg["pairs_by_variant"]
    seen = [v for v in VARIANTS if v != "first_party"]
    dele = [v for v in DELETIONS]
    w = 14
    head = f"{'rule':<26}" + "".join(f"{v:>{w}}" for v in seen)
    head += f"{'deletions':>{w}}{'all':>{w}}"
    n_del = sum(pairs.get(v, 0) for v in dele)
    n_all = sum(pairs.get(v, 0) for v in seen)
    out = [
        f"records {m['records']}; {lg['titles']} real case titles with a 'v'",
        "",
        "FALSE POSITIVES: a real, retrieved case written differently, REJECTED (%)",
        head,
        f"{'(pairs)':<26}"
        + "".join(f"{pairs.get(v, 0):>{w}}" for v in seen)
        + f"{n_del:>{w}}{n_all:>{w}}",
    ]
    for name, rej in lg["rejected"].items():
        row = f"{name:<26}"
        row += "".join(f"{pct(rej.get(v, 0), pairs.get(v, 0)):>{w}}" for v in seen)
        row += f"{pct(sum(rej.get(v, 0) for v in dele), n_del):>{w}}"
        row += f"{pct(sum(rej.get(v, 0) for v in seen), n_all):>{w}}"
        out.append(row)
    t = fb["trials"]
    out += [
        "",
        "FALSE NEGATIVES: a name for a case NOT retrieved, ACCEPTED (% of trials)",
        f"{'rule':<26}{'invented':>12}{'unretrieved':>14}{'swapped':>12}{'generic':>10}",
        f"{'(trials)':<26}{t['invented']:>12}{t['unretrieved']:>14}"
        f"{t['swapped']:>12}{t['generic']:>10}",
    ]
    for name, acc in fb["accepted"].items():
        out.append(
            f"{name:<26}{pct(acc['invented'], t['invented']):>12}"
            f"{pct(acc['unretrieved'], t['unretrieved']):>14}"
            f"{pct(acc['swapped'], t['swapped']):>12}"
            f"{pct(acc['generic'], t['generic']):>10}"
        )
    labs = ["X", "X & Ors.", "X & Anr.", "X Ltd.", "M/s X & Co."]
    out += ["", "INVENTED names accepted, by the suffix pattern (200 trials each)"]
    out.append(f"{'rule':<26}" + "".join(f"{lab:>13}" for lab in labs))
    for name, byp in fb["invented_by_pattern"].items():
        if name.startswith(
            ("a ", "b ", "c  ordered >= 0.8", "c  ordered >= 0.9", "d ", "e ", "f ")
        ):
            out.append(
                f"{name:<26}"
                + "".join(f"{pct(byp[lab], fb['pattern_trials']):>13}" for lab in labs)
            )
    out += [
        "",
        f"first party only (no 'v'): {pairs.get('first_party', 0)} pairs. No rule "
        "looks at a name without a 'v'; rule a accepts all of them, real or invented.",
    ]
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--write-generic", type=Path, help="write the generic-word list")
    ap.add_argument(
        "--titles", type=Path, help="records with a `title` (default: fixtures)"
    )
    a = ap.parse_args(argv)
    if a.write_generic:
        recs = read_records(a.titles) if a.titles else default_records()
        src = (
            str(a.titles)
            if a.titles
            else "practice fixtures (tests/fixtures/practice), a sample"
        )
        doc = write_generic_words(a.write_generic, recs, src)
        print(
            f"wrote {a.write_generic}: {len(doc['words'])} words from "
            f"{doc['case_titles']} titles"
        )
        return 0
    m = measure()
    print(render(m))
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(m, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
