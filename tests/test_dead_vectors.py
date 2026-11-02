"""The dead-vector detector: saved direction and scoring (data/dead_vectors/)."""

import importlib.util
import json
from pathlib import Path

import numpy as np

DIR = Path(__file__).resolve().parents[1] / "data" / "dead_vectors"
spec = importlib.util.spec_from_file_location(
    "score_dense_vectors", DIR / "score_dense_vectors.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_direction_is_a_saved_unit_1024_vector_with_recorded_sources():
    d = mod.load_direction()
    assert d.shape == (1024,) and abs(np.linalg.norm(d) - 1.0) < 1e-9
    meta = json.loads((DIR / "legal_direction_sources.json").read_text())
    assert (
        meta["n_sources"] == len(meta["sources"]) == 2694 and meta["threshold"] == 0.10
    )


def test_score_is_the_cosine_with_the_direction():
    d = mod.load_direction()
    rng = np.random.default_rng(0)
    other = rng.normal(size=1024)
    other -= other @ d * d  # exactly orthogonal to the direction
    s = mod.score(np.array([d * 3.0, other, -d]), d)
    assert np.allclose(s, [1.0, 0.0, -1.0], atol=1e-9)
    assert s[1] < mod.THRESHOLD


def test_random_vectors_are_flagged_and_real_directions_are_not():
    d = mod.load_direction()
    rng = np.random.default_rng(1)
    random_vecs = rng.normal(size=(200, 1024))
    assert (
        mod.score(random_vecs, d) < mod.THRESHOLD
    ).mean() > 0.99  # noise scores ~0 +/- 0.03
    near = d + 0.3 * rng.normal(size=(50, 1024)) / np.sqrt(1024)
    assert (mod.score(near, d) > mod.THRESHOLD).all()


def _fake_scroll(points):
    """A stand-in for the Qdrant scroll: ascending ids, `limit` per page, next_page_offset."""
    calls = []

    def scroll(base, collection, body):
        calls.append(body.get("offset"))
        start = body.get("offset") or 0
        page = [p for p in points if p["id"] >= start][: body["limit"]]
        rest = [p for p in points if p["id"] >= start][body["limit"] :]
        return {"points": page, "next_page_offset": rest[0]["id"] if rest else None}

    return scroll, calls


def _points(n):
    rng = np.random.default_rng(2)
    return [
        {
            "id": 10 * (k + 1),
            "vector": {"dense": rng.normal(size=1024).tolist()},
            "payload": {
                "chunk_id": f"C{k}",
                "char_start": 0,
                "char_end": 100,
                "chunk_index": k,
            },
        }
        for k in range(n)
    ]


def test_a_full_scan_walks_the_whole_collection_in_order_exactly_once(
    tmp_path, monkeypatch
):
    pts = _points(450)
    scroll, calls = _fake_scroll(pts)
    monkeypatch.setattr(mod, "scroll", scroll)
    monkeypatch.setattr(mod, "PAUSE_S", 0)
    out = tmp_path / "scan.tsv"
    monkeypatch.setattr(
        "sys.argv", ["x", "--collection", "c", "--court", "K", "--out", str(out)]
    )
    mod.main()
    ids = [int(line.split("\t")[0]) for line in out.read_text().splitlines()]
    assert ids == [p["id"] for p in pts]  # all 450, ascending, no repeats
    assert calls == [None, 2010, 4010]  # sequential pages, never random offsets
    assert json.loads(Path(str(out) + ".state").read_text())["done"] is True


def test_a_sample_scan_uses_random_offsets(tmp_path, monkeypatch):
    scroll, calls = _fake_scroll(_points(450))
    monkeypatch.setattr(mod, "scroll", scroll)
    monkeypatch.setattr(mod, "PAUSE_S", 0)
    out = tmp_path / "s.tsv"
    monkeypatch.setattr(
        "sys.argv",
        [
            "x",
            "--collection",
            "c",
            "--court",
            "K",
            "--sample",
            "200",
            "--out",
            str(out),
        ],
    )
    mod.main()
    assert calls and all(
        c is not None and c > 10**6 for c in calls
    )  # random 63-bit starts
