"""The serving-collection MANIFEST (A183): refuses originals, counts add up, and a removed gold
label is flagged. Pure tests: no Qdrant, no network."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from data import build_serving_collection_v3 as v3

ROOT = Path(__file__).resolve().parents[1]


def chunk(act, cid, **kw):
    base = {
        "act_id": f"IND_SUPP_{act}",
        "chunk_id": cid,
        "section_status": "not_checked",
        "section_type": "section",
    }
    return {**base, **kw}


def test_counts_add_up_and_one_source_per_act():
    removed = {"IND_central_2187": ["a", "b", "c"], "IND_central_2191": ["d"]}
    chunks = [
        chunk("contract1872", "IND_SUPP_contract1872_s1"),
        chunk("contract1872", "IND_SUPP_contract1872_s2"),
        chunk("constitution", "IND_SUPP_constitution_art1"),
        chunk("hma1955", "IND_SUPP_hma1955_s1"),
        chunk("crpc1973", "IND_SUPP_crpc1973_s1"),
    ]  # not wanted: stays out
    m = v3.plan(100, removed, chunks, [])
    assert m["kept"] == 96 and m["removed"] == 4
    assert m["supplement_added"] == 4 and m["final_count"] == 100
    assert m["source_kind"] == {"dataset": 96, "supplement_indiacode": 4}
    assert m["added_ids_without_supp_prefix"] == 0 and m["duplicate_ids_in_added"] == 0
    assert m["per_act"]["contract1872"]["removed_points"] == 3


def test_stamp_schedule_and_state_blocks_stay_off():
    chunks = [
        chunk("stamp1899", "s1"),
        chunk("stamp1899", "sa5", section_type="schedule_article"),
        chunk("stamp1899", "blk", section_type="schedule", state_amendment=True),
    ]
    m = v3.plan(10, {"IND_central_15510": ["x"]}, chunks, [])
    assert m["supplement_added"] == 1 and m["supplement_held_off"] == 2
    assert set(m["held_off_reasons"]) == {
        "stamp Schedule I: duty column not reliably attached to its row",
        "stamp state-amendment block: held until reviewed",
    }


def test_a_gold_label_on_a_removed_record_is_flagged():
    removed = {"IND_central_2191": ["IND_central_2191_s011_d15"]}
    qs = [
        {
            "id": "q1",
            "status": "ready",
            "expect_records": ["IND_central_2191_s011_d15"],
            "must_not_cite": [],
        },
        {
            "id": "q2",
            "status": "ready",
            "expect_records": ["2019_INSC_9001_000"],
            "must_not_cite": [],
        },
    ]
    hits = v3.plan(5, removed, [], qs)["eval_gold_labels_pointing_at_removed_ids"]
    assert [h["id"] for h in hits] == ["q1"]


@pytest.mark.parametrize(
    "args",
    [
        ["--collection", "kanoon_v1"],
        ["--collection", "legal_corpus_v2"],
        [],
        ["--collection", "research_v3", "--url", "http://localhost:6333"],
    ],
)
def test_the_guard_refuses_originals_no_collection_and_port_6333(args, tmp_path):
    f = tmp_path / "c.jsonl"
    f.write_text("")
    r = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "data/build_serving_collection_v3.py",
            *args,
            "--supplement-chunks",
            str(f),
            "--out-dir",
            str(tmp_path / "o"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0 and "ABORT" in r.stderr + r.stdout
    assert not (tmp_path / "o").exists()
