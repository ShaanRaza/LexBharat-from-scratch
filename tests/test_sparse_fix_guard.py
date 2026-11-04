"""data/sparse_fix.py must refuse every original named in CLAUDE.md section 6 and the original
instance, and must not run without --collection (it used to default to acts_india on 6333)."""

import subprocess
import sys
from pathlib import Path

import pytest

from data import sparse_fix

ROOT = Path(__file__).resolve().parents[1]
ORIGINALS = ["legal_corpus_v1", "legal_corpus_v2", "acts_india", "kanoon_v1"]


@pytest.mark.parametrize("name", ORIGINALS)
def test_every_original_is_refused(name):
    with pytest.raises(SystemExit) as e:
        sparse_fix.check_target(name, "http://localhost:7333")
    assert "original" in str(e.value)


@pytest.mark.parametrize("name", [None, ""])
def test_a_missing_collection_is_refused(name):
    with pytest.raises(SystemExit):
        sparse_fix.check_target(name, "http://localhost:7333")


def test_the_original_instance_is_refused_even_for_a_copy_name():
    with pytest.raises(SystemExit):
        sparse_fix.check_target("acts_noncentral_v1", "http://localhost:6333")


def test_a_copy_on_the_copy_instance_is_allowed():
    assert sparse_fix.check_target("acts_noncentral_v1", "http://localhost:7333/") == (
        "acts_noncentral_v1",
        "http://localhost:7333",
    )


def test_the_protected_set_is_the_four_originals_the_owner_named():
    assert sparse_fix.PROTECTED == frozenset(ORIGINALS)


def test_every_protected_name_is_documented_as_an_original():
    """CLAUDE.md section 6 does not spell the list out; the rule is written in the data docs."""
    text = (ROOT / "docs" / "DATA-GAPS.md").read_text() + (
        ROOT / "docs" / "QDRANT-INVENTORY.md"
    ).read_text()
    for name in sparse_fix.PROTECTED:
        assert name in text


@pytest.mark.parametrize(
    "args", [[], ["--collection", "acts_india"], ["--collection", "kanoon_v1"]]
)
def test_running_the_script_with_no_or_an_original_collection_exits_before_any_request(
    args,
):
    """Run for real: a nonzero exit and the guard's message, with an unreachable URL so a
    request would fail differently."""
    r = subprocess.run(  # noqa: S603 (fixed argv, no shell)
        [
            sys.executable,
            "-I",
            str(ROOT / "data" / "sparse_fix.py"),
            "plan",
            "--url",
            "http://127.0.0.1:1",
            *args,
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=60,
    )
    assert r.returncode != 0
    assert "ABORT" in r.stderr + r.stdout
