"""Court from the record id (CLAUDE.md section 6; pipeline step 5, Search).

Checks the identification table (30 prefixes, 26 courts, built from measured counts), the
lookup (nothing guessed), the label classification, and the backfill that writes
`court_code` beside the label (data/add_court_code.py, planning only: no Qdrant here).
"""

from __future__ import annotations

import csv
import json

import pytest

from core import court_id
from data import add_court_code, build_court_ids

T = court_id.load()
RAW = json.loads(court_id.PATH.read_text())

# The 30 prefixes, as measured across all 32,572,660 judgment rows (3 Nov 2026).
PREFIXES = {
    "APHC", "BRHC", "CGHC", "DLHC", "GAHC", "GJHC", "HBHC", "HCBM", "HCMA", "HCMD",
    "HPHC", "JHHC", "JKHC", "KAHC", "KLHC", "MLHC", "MNHC", "MPHC", "ODHC", "PHHC",
    "RJHC", "SKHC", "TRHC", "UKHC", "UPHC", "WBCHCA", "WBCHCJ", "WBCHCO", "WBCHCP",
    "INSC",
}  # fmt: skip


# --- the table ---------------------------------------------------------------------------
def test_the_table_holds_exactly_the_30_measured_prefixes_each_in_one_court():
    assert set(T.by_code) == PREFIXES and len(T.by_code) == 30
    assert len(T.courts) == 26
    assert sorted(c for ct in T.courts.values() for c in ct.codes) == sorted(PREFIXES)


def test_a_court_can_have_several_prefixes_and_they_are_the_benches_of_one_court():
    assert set(T.courts["calcutta"].codes) == {"WBCHCA", "WBCHCJ", "WBCHCO", "WBCHCP"}
    assert set(T.courts["madras"].codes) == {"HCMA", "HCMD"}
    assert T.courts["supreme-court"].codes == ("INSC",)


def test_the_totals_are_the_ones_section_18_reports():
    t = T.totals
    assert t["rows"] == 32_572_660
    assert (t["usual"], t["alias"], t["missing"], t["other_court"]) == (
        32_315_460,
        67_598,
        189_320,
        282,
    )
    assert t["usual"] + t["alias"] + t["missing"] + t["other_court"] == t["rows"]


def test_every_courts_rows_add_up_from_its_prefixes_and_its_label_kinds():
    for cid, c in RAW["courts"].items():
        assert sum(c["prefixes"].values()) == c["rows"], cid
        assert sum(c["label_rows"].values()) == c["rows"], cid


def test_the_table_is_what_the_builder_makes_from_the_committed_counts():
    """Not stale and not hand-edited (python data/build_court_ids.py rewrites it)."""
    assert json.dumps(build_court_ids.build(), indent=1, ensure_ascii=False) + "\n" == court_id.PATH.read_text()


def test_the_counts_file_has_30_prefixes_each_in_one_source_file():
    rows = list(csv.DictReader((build_court_ids.COUNTS).open()))
    src_of = {}
    for r in rows:
        src_of.setdefault(r["id_prefix"] or "INSC", set()).add(r["source_file"])
    assert set(src_of) == PREFIXES and all(len(v) == 1 for v in src_of.values())


# --- the id -> court derivation ------------------------------------------------------------
@pytest.mark.parametrize("code", sorted(PREFIXES - {"INSC"}))
def test_each_letter_prefix_derives_its_court(code):
    rid = f"{code}010123452021_007"
    assert court_id.code_from_record_id(rid) == code
    assert code in court_id.court_from_record_id(rid).codes


def test_the_supreme_court_has_no_letter_prefix_and_is_read_from_its_id_shape():
    for rid in ("1964_INSC_115_015", "2024_INSC_101_003", "1973_INSC_91_638"):
        assert court_id.code_from_record_id(rid) == "INSC"
        assert court_id.court_from_record_id(rid).id == "supreme-court"


@pytest.mark.parametrize(
    "rid",
    [
        None, "", 12, "IND_central_1", "IND_REP_9", "2020_INSC_x_1", "klhc010123452021_001",
        "XXHC010123452021_001", "KLHC", "KLHCxx", "99_INSC_1_1", "ABC", "_INSC_1_1",
    ],
)  # fmt: skip
def test_an_id_that_matches_no_prefix_has_no_court_and_nothing_is_guessed(rid):
    assert court_id.code_from_record_id(rid) is None
    assert court_id.court_from_record_id(rid) is None


# --- labels ---------------------------------------------------------------------------------
def test_labels_are_classified_against_the_court_the_id_names():
    k = court_id.classify_label
    assert k("KLHC010123452021_001", T.courts["kerala"].label) == "usual"
    assert k("KLHC010123452021_001", None) == "missing"
    assert k("KLHC010123452021_001", "   ") == "missing"
    assert k("APHC010123452021_001", "High Court of Amaravati") == "alias"
    # the real pattern behind 71 of the 282: a Delhi record labelled with another court
    assert k("DLHC010123452021_001", "High Court of Patna") == "other_court"
    assert k("IND_central_1", "anything") == "unknown_id"


def test_a_label_names_a_court_only_when_it_names_exactly_one():
    f = court_id.court_for_label
    assert f("Supreme Court of India").id == "supreme-court"
    assert f("  high court   OF kerala ").id == "kerala"  # case and spacing do not matter
    assert f("High Court  for State of Telangana").id == "telangana"
    assert f("High Court of Hyderabad") is None  # shared by two courts
    assert f("High Court") is None  # names no place
    assert f("Some Tribunal") is None and f("") is None and f(None) is None and f(5) is None


def test_every_registered_label_that_names_one_court_finds_that_court():
    for c in T.courts.values():
        got = court_id.court_for_label(c.label)
        assert got is not None and got.id == c.id, c.id


def test_an_unregistered_court_id_raises_instead_of_defaulting():
    with pytest.raises(KeyError):
        court_id.court("a-tribunal-nobody-registered")


def test_the_original_label_is_kept_the_table_records_the_other_court_labels():
    delhi = RAW["courts"]["delhi"]
    assert "High Court of Patna" in delhi["other_court_labels"]  # kept as data, never merged in


# --- the backfill: planning only ------------------------------------------------------------
def _pt(i, chunk_id, court=None, court_code=None):
    pay = {"chunk_id": chunk_id}
    if court is not None:
        pay["court"] = court
    if court_code is not None:
        pay["court_code"] = court_code
    return {"id": i, "payload": pay}


def test_the_plan_derives_beside_the_label_and_counts_what_a_label_filter_would_drop():
    pts = [
        _pt(1, "KLHC010123452021_001", "High Court of Kerala"),  # usual
        _pt(2, "KLHC010123452021_002"),  # no label at all
        _pt(3, "APHC010123452021_001", "High Court of Amaravati"),  # a spelling variant
        _pt(4, "DLHC010123452021_001", "High Court of Patna"),  # another court's name
        _pt(5, "1964_INSC_115_015", "Supreme Court of India", "INSC"),  # already done
        _pt(6, "IND_central_1_s2", None),  # an Act: not a judgment
    ]
    pl = add_court_code.plan(pts)
    assert pl.scanned == 6
    assert dict(pl.updates) == {"KLHC": [1, 2], "APHC": [3], "DLHC": [4]}
    assert pl.already == 1 and pl.to_write == 4
    assert pl.kinds["usual"] == 2 and pl.kinds["missing"] == 1 and pl.kinds["alias"] == 1
    assert pl.kinds["other_court"] == 1 and pl.kinds["unknown_id"] == 1
    assert pl.label_filter_would_drop == 3  # the missing, the variant and the foreign label
    assert pl.conflicts == [(4, "DLHC010123452021_001", "High Court of Patna", "DLHC")]


def test_the_plan_is_idempotent_a_second_pass_writes_nothing():
    first = add_court_code.plan([_pt(1, "KLHC010123452021_001"), _pt(2, "1952_INSC_28_078")])
    done = [_pt(1, "KLHC010123452021_001", None, "KLHC"), _pt(2, "1952_INSC_28_078", None, "INSC")]
    second = add_court_code.plan(done)
    assert first.to_write == 2 and second.to_write == 0 and second.already == 2


def test_the_plan_never_proposes_changing_the_label():
    pl = add_court_code.plan([_pt(4, "DLHC010123452021_001", "High Court of Patna")])
    assert list(pl.updates) == ["DLHC"]  # a court_code, and only that


def test_the_script_refuses_the_original_collections(monkeypatch):
    calls = []
    monkeypatch.setattr(add_court_code, "http", lambda *a, **k: calls.append(a))
    for name in ("legal_corpus_v1", "legal_corpus_v2", "acts_india"):
        monkeypatch.setattr("sys.argv", ["add_court_code.py", name, "--apply"])
        with pytest.raises(SystemExit) as e:
            add_court_code.main()
        assert "REFUSED" in str(e.value)
    assert calls == []  # not even a read
