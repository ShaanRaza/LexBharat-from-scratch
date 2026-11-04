"""Validate the Haiku paraphrases (same validator as the question-style retest: no digit, no reused capitalised name, no 4-word run from the chunk, 8-40 words ending '?') and merge with the sentence queries into c_queries.json."""

import collections
import glob
import json
import re

from evals.a136.paths import DATA as S

T = json.load(open(f"{S}/c_targets.json"))
text = {int(k): v for k, v in T["text"].items()}


def body(t):
    return t.split("\n\n", 1)[1] if "\n\n" in t else t


def W(s):
    return re.findall(r"[a-z0-9]+", s.lower())


OK = {
    "court",
    "act",
    "article",
    "constitution",
    "india",
    "indian",
    "high",
    "supreme",
    "section",
    "code",
    "state",
    "government",
    "what",
    "when",
    "whether",
    "how",
    "why",
    "can",
    "does",
    "is",
    "are",
    "who",
    "which",
    "under",
    "in",
    "if",
    "may",
    "must",
    "should",
    "do",
    "did",
    "will",
    "would",
    "a",
    "an",
    "the",
    "i",
}


def leaks(q, chunk):
    r = []
    if re.search(r"\d", q):
        r.append("digits")
    cc = set(re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", chunk))
    bad = [
        t
        for t in re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", q)[1:]
        if t in cc and t.lower() not in OK
    ]
    if bad:
        r.append("names")
    cw, qw = W(chunk), W(q)
    g4 = {tuple(cw[i : i + 4]) for i in range(len(cw) - 3)}
    if any(tuple(qw[i : i + 4]) in g4 for i in range(len(qw) - 3)):
        r.append("4gram")
    if not (8 <= len(qw) <= 40) or not q.strip().endswith("?"):
        r.append("format")
    return r


cand = collections.defaultdict(list)
for f in sorted(glob.glob(f"{S}/qgen/out_*.json")):
    for k, qs in json.load(open(f)).items():
        cand[int(k)] += [q for q in qs if isinstance(q, str)]
code = {t["id"]: t["code"] for t in T["targets"]}
Q = list(T["Q"])
total = rej = 0
reasons = collections.Counter()
per = collections.Counter()
for tid, c in code.items():
    good = []
    for q in cand.get(tid, []):
        total += 1
        r = leaks(q, body(text[tid]))
        if r:
            rej += 1
            reasons.update(r)
        elif q not in good and len(good) < 2:
            good.append(q)
    per[len(good)] += 1
    for q in good:
        Q.append({"id": tid, "code": c, "style": "paraphrase", "text": q})
print(
    f"paraphrases received {total}; rejected {rej} ({rej / max(total, 1) * 100:.1f}%) {dict(reasons)}; targets with 2 valid {per[2]}, 1 valid {per[1]}, 0 valid {per[0]} of {len(code)}"
)
print("queries:", collections.Counter(q["style"] for q in Q))
json.dump(Q, open(f"{S}/c_queries.json", "w"))
