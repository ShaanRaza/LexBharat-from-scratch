import json

from fastembed import SparseTextEmbedding

from evals.a136.paths import DATA as S

Q = json.load(open(f"{S}/c_queries.json"))
enc = SparseTextEmbedding(model_name="Qdrant/bm25")
out = {}
for q in Q:
    if q["text"] not in out:
        e = next(iter(enc.query_embed([q["text"]])))
        out[q["text"]] = ([int(i) for i in e.indices], [float(v) for v in e.values])
json.dump(out, open(f"{S}/c_sparse.json", "w"))
print(len(out), "sparse query vectors")
