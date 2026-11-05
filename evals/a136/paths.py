"""Where the A136 evidence scripts read and write (see README.md).

Run every script from the repo root as a module, e.g. `.venv/bin/python -m evals.a136.c_analyze`.
"""

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# Small evidence, in git: the 1,161 queries, the per-query ranks, the court facets used to
# weight by volume, and the paraphrases the Haiku writers returned.
RESULTS = Path(__file__).resolve().parent / "results"
# Larger inputs and outputs (query vectors, targets, corpus metadata), NOT in git.
DATA = Path(os.environ.get("A136_DATA", "~/qdrant-kanoon/a128_confirm")).expanduser()
