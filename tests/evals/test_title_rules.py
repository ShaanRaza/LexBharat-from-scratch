"""The stricter-rule measurement (A116). It must use the real verifier for rule a, and
its candidate rules must behave as described, or its numbers describe something else."""

import pytest

import core.verify as v
from evals import title_rules as tr


def test_rule_a_is_the_real_verifier_function():
    assert tr._unretrieved_authority is v._unretrieved_authority


def test_shortenings_of_a_real_title():
    left, right = tr.split_title(
        "M/S. SARUPCHAND HUKAMCHAND & CO. versus UNION OF INDIA AND OTHERS"
    )
    # ("&" is dropped by the verifier's own normaliser, so it is not a token)
    short = tr.shorten
    assert short(left, right, "drop_ms") == (
        "sarupchand hukamchand co v union of india and others".split()
    )
    assert short(left, right, "drop_ors") == (
        "m s sarupchand hukamchand co v union of india".split()
    )
    assert short(left, right, "surname_first") == (
        "sarupchand v union of india and others".split()
    )
    assert short(left, right, "surname_last") == (
        "hukamchand v union of india and others".split()
    )
    assert short(left, right, "first_party")[-1] == "co"  # no "v": nothing to check
    assert short(left, right, "drop_anr") is None  # nothing to drop: not a shortening


def test_the_two_surface_styles_differ_the_way_the_verifier_reads_them():
    toks = "smith and ors v state of kerala".split()
    assert tr.written(toks) == "Smith & Ors. v. State of Kerala"
    assert tr.written(toks, "titlecase") == "Smith And Ors v. State Of Kerala"


def _recs(*titles_and_text):
    rows = [
        {"chunk_id": f"r{i}", "title": t, "text": b, "section_number": None}
        for i, (t, b) in enumerate(titles_and_text)
    ]
    for r in rows:
        del r["section_number"]
    return tr.build(rows)


def test_candidate_rules_on_a_toy_retrieved_set():
    recs = _recs(("SMITH AND CO. versus UNION OF INDIA", "Some body text."))
    ok_sub = "smith v union of india".split()  # a subsequence of the title
    swapped = "union of india v smith and co".split()
    invented = "zorblax and co v union of india".split()
    assert not tr.rule_b(ok_sub, recs)  # b needs the whole run
    assert tr.make_rule_c(1.0)(ok_sub, recs)
    assert not tr.make_rule_c(1.0)(swapped, recs)  # order matters
    assert tr.make_rule_c(1.0, ordered=False)(swapped, recs)  # a bag of words does not
    assert not tr.make_rule_c(1.0)(invented, recs)
    assert tr.make_rule_c(0.6)(invented, recs)  # a loose threshold lets it through


def test_a_character_tolerant_rule_forgives_a_slip_and_an_abbreviation():
    recs = _recs(("SARUPCHAND HUKAMCHAND AND CO. versus UNION OF INDIA", "Body."))
    slip = "sarupchxnd hukamchand and co v union of india".split()
    longform = "sarupchand hukamchand and company v union of india".split()
    assert not tr.make_rule_c(1.0)(slip, recs)
    assert tr.make_rule_d(1.0)(slip, recs)
    assert tr.make_rule_d(1.0)(longform, recs)


def test_a_name_of_only_generic_words_is_rejected_by_e_and_f():
    recs = _recs(("STATE OF KERALA versus UNION OF INDIA", "Body."))
    generic = ["state", "v", "union"]
    assert tr.make_rule_c(1.0)(generic, recs)  # the loophole in c
    common = ["state", "union", "of", "india", "kerala", "co", "ltd", "ors"]
    assert not tr.make_rule_e(common)(generic, recs)
    assert not tr.make_rule_e(common, fuzzy=True)(generic, recs)


@pytest.fixture(scope="module")
def result():
    return tr.measure(max_titles=150, scale=0.2)


def test_the_reported_findings_hold(result):
    fp = {k: v for k, v in result["legitimate"]["rejected"].items()}
    pairs = result["legitimate"]["pairs_by_variant"]
    dele = sum(pairs[k] for k in tr.DELETIONS)
    rate = lambda name: sum(fp[name].get(k, 0) for k in tr.DELETIONS) / dele  # noqa: E731
    acc = result["fabricated"]["accepted"]
    t = result["fabricated"]["trials"]
    # no stricter rule rejects a pure deletion of a retrieved title, ordered c at 1.0
    assert rate("c  ordered >= 1.0") == 0
    # a bag of words accepts every party-swapped name; order-aware rules do not
    assert acc["c' bag of words = 1.0"]["swapped"] == t["swapped"]
    assert acc["c  ordered >= 1.0"]["swapped"] == 0
    # the generic-word loophole exists in c and is closed in e and f
    assert acc["c  ordered >= 1.0"]["generic"] > 0
    assert acc["e  c 1.0 + a distinctive word"]["generic"] == 0
    assert acc["f  d 1.0 + a distinctive word"]["generic"] == 0
    # e and f accept no fabricated name of any kind in this sample
    for rule in ("e  c 1.0 + a distinctive word", "f  d 1.0 + a distinctive word"):
        assert all(acc[rule][k] == 0 for k in t)
