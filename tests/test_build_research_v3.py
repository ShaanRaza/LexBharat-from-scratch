# ruff: noqa: S603
"""research_v3 builder (A184): heading_section reads the chunk's own heading, ids are stable, and the
guard refuses originals. No Qdrant, no Voyage."""

import subprocess
import sys
from pathlib import Path

import pytest

from data import build_research_v3 as b

ROOT = Path(__file__).resolve().parents[1]


def test_kanoon_heading_is_read_from_the_header_not_from_section_number():
    p = {
        "section_number": "3",
        "text": "Act: X | India | Central | In Force\nChapter V: A | Section 11: _Appeals_\n\nbody",
    }
    assert b.heading_section(p) == "11"
    assert (
        b.heading_section({"text": "Act: X\nArticle 21A: Right to education\nbody"})
        == "21A"
    )
    assert (
        b.heading_section({"text": "2019_INSC_1_000 a judgment with no heading"}) == ""
    )


def test_supplement_orders_are_kept_apart_from_sections():
    base = {"source_kind": "supplement_indiacode", "section_number": "11"}
    assert b.heading_section({**base, "section_type": "section"}) == "11"
    assert (
        b.heading_section({**base, "section_type": "rule", "order_number": "VII"})
        == "Order VII Rule 11"
    )
    r2 = {**base, "section_type": "rule", "order_number": "XI", "order_variant": 2}
    assert b.heading_section(r2) == "Order XI Rule 11 (variant 2)"
    assert (
        b.heading_section({**base, "section_type": "schedule_article"})
        == "Schedule Article 11"
    )


def test_point_ids_are_stable_distinct_and_in_range():
    ids = {b.point_id(f"IND_SUPP_x_s{i}") for i in range(2000)}
    assert len(ids) == 2000 and all(0 <= i < 2**63 for i in ids)
    assert b.point_id("a") == b.point_id("a")


@pytest.mark.parametrize(
    "args",
    [
        ["--target", "kanoon_v1"],
        ["--target", "acts_india"],
        [],
        ["--target", "research_v3", "--url", "http://localhost:6333"],
    ],
)
def test_guard_refuses_originals_and_6333(args, tmp_path):
    r = subprocess.run(
        [
            sys.executable,
            "data/build_research_v3.py",
            "copy",
            *args,
            "--state",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )  # noqa: S603
    assert r.returncode != 0 and "ABORT" in r.stdout + r.stderr
