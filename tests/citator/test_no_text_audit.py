"""The two pure helpers of the no-text audit (scan/sc/no_text_audit.py)."""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "no_text_audit",
    Path(__file__).resolve().parents[2] / "scan" / "sc" / "no_text_audit.py",
)
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


def test_body_words_ignores_the_header():
    text = "Case: A versus B [[1950] 1 S.C.R. 1] (1950)\nSection: BODY\n\nThe appeal is dismissed with costs."
    assert audit.body_words(text) == 6


def test_empty_body_has_no_words():
    assert audit.body_words("Case: A versus B\nSection: BODY\n\n") == 0
    assert audit.body_words("") == 0


def test_classify_boxes():
    served, en = {"a", "b"}, {"a"}
    assert audit.classify("a", served, en) == "served_with_text_in_source"
    assert audit.classify("b", served, en) == "served_not_english_in_source"
    assert audit.classify("c", served, en) == "not_served"
