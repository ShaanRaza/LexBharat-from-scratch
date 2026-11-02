"""The dead-vector detector's saved direction and scoring function (data/dead_vectors/)."""

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
