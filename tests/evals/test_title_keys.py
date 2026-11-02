"""The named-case key measurement of the OLD rule (A113, result A115; retired from the
verifier by A117). It must still use the verifier's own pieces."""

import core.verify as v
from evals import title_keys as tk


def test_it_uses_the_verifiers_own_functions_not_copies():
    assert tk._VERSUS_CORE is v._VERSUS_CORE
    assert tk._norm_case_name is v._norm_case_name


def test_keys_are_one_word_either_side_of_v():
    k = tk.keys_of("M/S. SARUPCHAND HUKAMCHAND & CO. versus UNION OF INDIA AND OTHERS")
    assert k == ["co v union"]
    assert tk.keys_of("HANSRAJ MOOLJI versus THE STATE OF BOMBAY") == ["moolji v the"]
    assert tk.keys_of("The Bharatiya Sakshya Adhiniyam, 2023") == []  # an Act: no key
    assert tk.keys_of("Article 14 v. 19") == []  # the verifier skips numbers


def test_shared_share_and_top_keys_on_a_toy_corpus():
    rows = [
        {"title": "A AND ORS. versus STATE OF X"},
        {"title": "B AND ORS. versus STATE OF Y"},
        {"title": "SOMEONE versus THE UNION"},
    ]
    m = tk.measure(rows)
    assert m["titles_with_a_key"] == 3 and m["distinct_keys"] == 2
    assert m["share_of_titles_whose_key_is_shared"] == round(2 / 3, 4)
    assert m["top20_keys"][0]["key"] == "ors v state"
    assert m["share_of_titles_with_right_token_in"]["by_token"]["state"] == round(
        2 / 3, 4
    )


def test_reach_is_a_probability():
    assert tk.reach(0, 10, 3) == 0.0
    assert abs(tk.reach(1, 10, 1) - 0.1) < 1e-9
    assert tk.reach(10, 10, 3) == 1.0
