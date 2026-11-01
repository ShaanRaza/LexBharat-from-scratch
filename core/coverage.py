"""ONE source of truth for what v1 covers (decision O7, A51).

Plain words: what the product covers used to be typed by hand in six places that drifted
apart (the website, the scope checker, the decide prompt, the README ...), so the scope
checker refused questions the website promised. Now it is written ONCE, in
core/coverage.json, and every reader asks this file:

  * the scope criteria sent to Jev            -> scope_criteria()
  * the decide prompt (Gemini fallback)       -> scope_choices(), scope_help()
  * the sentence shown to users               -> coverage_sentence()
                                                 (API: GET /coverage)
  * the README and UX-COPY blocks             -> render_docs_block()
                                                 (python -m core.coverage --write-docs)
  * the Qdrant court filter value             -> court_payload()
  * the public coverage page                  -> GET /coverage

While `status` is "placeholder" the file holds a conservative guess. Once
data/coverage_report.py has measured the dataset it rewrites the file with
status "measured". No other file may hard-code a coverage category;
tests/test_coverage_source.py fails if one does.

Pipeline step touched: 3 (Decide) reads the scope criteria from here. Nothing else."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).with_name("coverage.json")
ROOT = PATH.parent.parent

# Scope buckets that are NOT about coverage and so are not in the JSON.
IN_SCOPE = "in_scope"
NOT_LEGAL = "not_legal"
NOT_IN_DATASET = "not_in_dataset"  # a source the dataset does not hold (O7)


@dataclass(frozen=True)
class Court:
    id: str
    name: str
    covered_label: str
    payload: dict[str, str]


@dataclass(frozen=True)
class Instrument:
    id: str
    covered_label: str
    payload: dict[str, str]


@dataclass(frozen=True)
class Coverage:
    status: str  # "placeholder" until data/coverage_report.py has run, then "measured"
    sentence_approved: (
        bool  # False = NEEDS-OWNER: the owner has not approved the wording
    )
    sentence_template: str
    not_in_dataset_message: str
    courts: tuple[Court, ...]
    instruments: tuple[Instrument, ...]
    excluded: tuple[str, ...]
    # scope bucket id -> criteria text (not the in-scope or not-in-dataset buckets)
    buckets: dict[str, str]
    measured_at: str | None = None
    generated_by: str | None = None

    @property
    def covered_labels(self) -> list[str]:
        return [c.covered_label for c in self.courts] + [
            i.covered_label for i in self.instruments
        ]


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _parse(raw: dict) -> Coverage:
    status = raw["status"]
    if status not in ("placeholder", "measured"):
        raise ValueError(f"coverage status must be placeholder or measured: {status!r}")
    if status == "measured" and not (
        raw.get("measured_at") and raw.get("generated_by")
    ):
        raise ValueError("a measured coverage file must say when and by what")
    courts = tuple(Court(**c) for c in raw["courts"])
    instruments = tuple(Instrument(**i) for i in raw["instruments"])
    if not courts and not instruments:
        raise ValueError("coverage names nothing: it must list what the data holds")
    buckets = dict(raw["buckets"])
    from typing import get_args

    from core.contracts import ScopeClass

    allowed = set(get_args(ScopeClass)) - {IN_SCOPE, NOT_LEGAL, NOT_IN_DATASET}
    if set(buckets) != allowed:
        raise ValueError(f"buckets must be exactly {sorted(allowed)}")
    return Coverage(
        status=status,
        sentence_approved=bool(raw["sentence_approved"]),
        sentence_template=raw["sentence_template"],
        not_in_dataset_message=raw["not_in_dataset_message"],
        courts=courts,
        instruments=instruments,
        excluded=tuple(raw["excluded"]),
        buckets=buckets,
        measured_at=raw.get("measured_at"),
        generated_by=raw.get("generated_by"),
    )


@lru_cache(maxsize=1)
def load_coverage() -> Coverage:
    return _parse(json.loads(PATH.read_text(encoding="utf-8")))


# --- what each reader gets ---------------------------------------------------------
def coverage_sentence(product_name: str, cov: Coverage | None = None) -> str:
    """The sentence shown to users. Built from the measured/placeholder categories.
    NEEDS-OWNER while `sentence_approved` is false."""
    cov = cov or load_coverage()
    return cov.sentence_template.format(
        product=product_name,
        covered=_join(cov.covered_labels),
        excluded=_join(list(cov.excluded)),
    )


def scope_criteria(cov: Coverage | None = None) -> dict[str, str]:
    """Scope bucket -> one-line criteria, for Jev and for the decide prompt."""
    cov = cov or load_coverage()
    return {
        IN_SCOPE: f"A legal question that {_join(cov.covered_labels)} can answer.",
        **cov.buckets,
        NOT_IN_DATASET: (
            "Needs a legal source that is not held in the dataset and is not one of "
            "the cases above."
        ),
        NOT_LEGAL: "Not a legal question.",
    }


def scope_choices(cov: Coverage | None = None) -> str:
    return "|".join(scope_criteria(cov))


def scope_help(cov: Coverage | None = None) -> str:
    return "\n".join(f"- {k}: {v}" for k, v in scope_criteria(cov).items())


def scope_question(cov: Coverage | None = None) -> str:
    cov = cov or load_coverage()
    what = _join(cov.covered_labels)
    return (
        f"Can a research tool covering {what} answer the user's question in "
        "state.question?"
    )


def court_payload(court_id: str, cov: Coverage | None = None) -> dict[str, str]:
    cov = cov or load_coverage()
    for c in cov.courts:
        if c.id == court_id:
            return dict(c.payload)
    raise KeyError(court_id)


# --- docs: README and UX-COPY read this too --------------------------------------
DOC_BLOCKS = {
    "README.md": "coverage",
    "docs/UX-COPY.md": "coverage-sentence",
}


def render_docs_block(name: str, product_name: str, cov: Coverage | None = None) -> str:
    cov = cov or load_coverage()
    sentence = coverage_sentence(product_name, cov)
    if name == "coverage":
        flag = (
            "placeholder, not yet measured"
            if cov.status == "placeholder"
            else f"measured {cov.measured_at}"
        )
        owner = "" if cov.sentence_approved else " (NEEDS-OWNER: wording not approved)"
        return (
            f"**Coverage ({flag}):** {sentence}{owner} "
            "Generated from `core/coverage.json`; do not edit by hand."
        )
    if name == "coverage-sentence":
        owner = "" if cov.sentence_approved else " **NEEDS-OWNER**"
        return f'"{sentence}"{owner} (generated from `core/coverage.json`)'
    raise KeyError(name)


def _replace_block(text: str, name: str, body: str) -> str:
    pat = re.compile(
        rf"(<!-- {re.escape(name)}:begin -->).*?(<!-- {re.escape(name)}:end -->)", re.S
    )
    if not pat.search(text):
        raise ValueError(f"no <!-- {name}:begin --> block")
    return pat.sub(lambda m: f"{m.group(1)}{body}{m.group(2)}", text)


def docs_in_sync(product_name: str) -> dict[str, bool]:
    out = {}
    for rel, name in DOC_BLOCKS.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        out[rel] = (
            _replace_block(text, name, render_docs_block(name, product_name)) == text
        )
    return out


def write_docs(product_name: str) -> None:
    for rel, name in DOC_BLOCKS.items():
        p = ROOT / rel
        p.write_text(
            _replace_block(
                p.read_text(encoding="utf-8"),
                name,
                render_docs_block(name, product_name),
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":  # python -m core.coverage [--write-docs | --check]
    from core.settings import Settings

    # The CODE default, not whatever a developer's .env says: the generated text must be
    # the same on every machine (and in CI).
    product = Settings.model_fields["PRODUCT_NAME"].default
    if "--write-docs" in sys.argv:
        write_docs(product)
        print("README.md and docs/UX-COPY.md updated from core/coverage.json")
    else:
        state = docs_in_sync(product)
        print(state)
        sys.exit(0 if all(state.values()) else 1)
