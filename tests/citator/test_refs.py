"""core/citator/refs.py: reference shapes seen in the OCR text of Supreme Court judgments."""

from core.citator.refs import extract, stored_citation_key


def kinds(text):
    return [(r.kind, r.key) for r in extract(text)]


def test_stored_field_forms():
    assert stored_citation_key("[2020] 12 S.C.R. 1") == (
        "scr",
        2020,
        False,
        12,
        False,
        1,
    )
    assert stored_citation_key("[2006] SUPP. 10 S.C.R. 885") == (
        "scr",
        2006,
        True,
        10,
        False,
        885,
    )


def test_scr_ocr_variants_give_one_key():
    for raw in (
        "[1985] 3 SCR 697",
        "(1985] 3 S.C.R. 697",
        "[1985] 3 S. C.R. 697",
        "1985 (3) SCR 697",
    ):
        assert kinds(raw) == [("scr", ("scr", 1985, False, 3, False, 697))], raw


def test_ocr_l_for_one():
    assert kinds("[1976] l S.C.R. 815")[0][1] == ("scr", 1976, False, 1, False, 815)


def test_supplementary_volume_forms():
    assert kinds("[1994] 6Suppl. SCR 316")[0][1] == ("scr", 1994, True, 6, False, 316)
    assert kinds("2003 (6) Suppl. SCR 1235")[0][1] == (
        "scr",
        2003,
        True,
        6,
        False,
        1235,
    )
    assert kinds("[1966] Suppl. SCR 311")[0][1] == ("scr", 1966, True, None, False, 311)


def test_volume_omitted_before_1955():
    assert kinds("[1950] S.C.R. 88")[0][1] == ("scr", 1950, False, None, False, 88)


def test_running_header_without_page_is_not_a_reference():
    assert kinds("SUPREME COURT REPORTS [2019] 3 S.C.R. A4. The appellant") == []


def test_neutral_forms():
    for raw in ("2018 INSC 329", "2023:INSC:1007", "2011/INSC/42223"):
        assert [k for k, _ in kinds(raw)] == ["neutral"], raw
    assert kinds("2018 INSC 329")[0][1] == ("neutral", 2018, 329)


def test_scc_forms_found_not_resolved():
    for raw in (
        "(2004) 12 SCC 376",
        "(1986) Supp SCC 617",
        "1992 Supp (1) SCC 217",
        "(1977) 2SCC 699",
    ):
        assert [k for k, _ in kinds(raw)] == ["scc"], raw


def test_parallel_citation_is_two_references():
    got = [k for k, _ in kinds("(2015) 6 SCC 652 : [2015] 5 SCR 1112")]
    assert got == ["scc", "scr"]


def test_air_supreme_court_vs_high_court():
    sc = extract("AIR 1959 SC 395")[0]
    hc = extract("AIR 1973 Madras 191")[0]
    assert (sc.kind, sc.note) == ("air", "air_sc")
    assert (hc.kind, hc.note) == ("air", "air_other_court")


def test_one_printed_citation_is_one_reference():
    assert len(extract("AIR 1950 SC 27")) == 1
