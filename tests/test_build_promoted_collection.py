"""data/build_promoted_collection.py must refuse the originals and the original instance."""

import pytest

from data import build_promoted_collection as b


@pytest.mark.parametrize(
    "target", ["kanoon_v1", "acts_india", "legal_corpus_v2", "legal_corpus_v1"]
)
def test_it_refuses_an_original_as_the_target(target):
    with pytest.raises(SystemExit):
        b.main(
            [
                "--target",
                target,
                "--source",
                "acts_noncentral_v1",
                "--state",
                "none.json",
            ]
        )


def test_it_refuses_the_original_instance():
    with pytest.raises(SystemExit):
        b.main(
            [
                "--target",
                "research_v2",
                "--source",
                "a",
                "--state",
                "none.json",
                "--url",
                "http://localhost:6333",
            ]
        )


def test_a_source_cannot_be_the_target():
    with pytest.raises(SystemExit):
        b.main(
            [
                "--target",
                "research_v2",
                "--source",
                "research_v2",
                "--state",
                "none.json",
            ]
        )
