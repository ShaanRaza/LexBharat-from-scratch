"""A128 eval step 2: 10 random targets per court code (from the corpus), their text read-only from the original, sentence-style queries (the check-4 recipe), and the paraphrase input files for the Haiku writers."""

import collections
import json
import random
import re

from evals.a136 import orig_ro as o
from evals.a136.paths import DATA as S

OLD = json.load(open(f"{S}/a128_targets.json"))["targets"]
OLDID = {t["id"] for t in OLD}
OLDDOC = {t["chunk_id"].rsplit("_", 1)[0] for t in OLD}
meta = json.load(open(f"{S}/a128_corpus_meta.json"))
by = collections.defaultdict(list)
for pid, pay in meta.items():
    if int(pid) in OLDID or pay["chunk_id"].rsplit("_", 1)[0] in OLDDOC:
        continue
    by[pay["court_code"]].append(int(pid))
rnd = random.Random(7701)
pick = []
for code, ids in sorted(by.items()):
    pick += [
        (code, i) for i in rnd.sample(ids, 14)
    ]  # a few spare: some chunks have no usable sentences
text = {}
for i in range(0, len(pick), 20):
    for p in o.q(
        "/collections/legal_corpus_v2/points",
        {
            "ids": [x for _, x in pick[i : i + 20]],
            "with_payload": ["text"],
            "with_vector": False,
        },
        f"txt {i}",
    ):
        text[p["id"]] = p["payload"]["text"]


def body_of(t):
    return t.split("\n\n", 1)[1] if "\n\n" in t else t


def sentences(t):
    return sorted(
        [
            s.strip()
            for s in re.split(r"(?<=[.;])\s+", re.sub(r"\s+", " ", body_of(t)))
            if 70 <= len(s.strip()) <= 260 and len(re.findall(r"[A-Za-z]{3,}", s)) >= 10
        ],
        key=len,
        reverse=True,
    )


def strip(s):
    return " ".join(
        x for x in s.split() if not re.search(r"\d", x) and not x[:1].isupper()
    )


targets, Q = [], []
per = collections.Counter()
for code, pid in pick:
    if per[code] >= 10:
        continue
    ss = sentences(text[pid])
    if len(ss) < 3 or len(text[pid]) < 700:
        continue
    per[code] += 1
    targets.append({"id": pid, "code": code, "chunk_id": meta[str(pid)]["chunk_id"]})
    Q.append({"id": pid, "code": code, "style": "sentence", "text": ss[0]})
    Q.append({"id": pid, "code": code, "style": "sentence", "text": ss[len(ss) // 2]})
    b = strip(ss[0])
    if len(b.split()) >= 8:
        Q.append({"id": pid, "code": code, "style": "sentence", "text": b})
print(
    len(targets),
    "targets over",
    len(per),
    "codes (per code:",
    dict(sorted(per.items())),
    ")",
    len(Q),
    "sentence-style queries",
)
json.dump(
    {
        "targets": targets,
        "Q": Q,
        "text": {str(k): v for k, v in text.items() if k in {t["id"] for t in targets}},
    },
    open(f"{S}/c_targets.json", "w"),
)
ids = [t["id"] for t in targets]
rnd.shuffle(ids)
for k in range(4):
    json.dump(
        [{"id": str(i), "passage": body_of(text[i])[:2200]} for i in ids[k::4]],
        open(f"{S}/qgen/in_{k}.json", "w"),
        ensure_ascii=False,
    )
print(
    "paraphrase batches:",
    [len(ids[k::4]) for k in range(4)],
    "| requests",
    len(o.LOG),
    "slowest %.1fs" % max(t for _, t in o.LOG),
)
