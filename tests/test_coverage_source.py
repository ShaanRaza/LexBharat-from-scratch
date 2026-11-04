"""One source of truth for what v1 covers (decision A51).

What v1 covers used to be typed by hand in a dozen places that drifted apart: the
website said "central and state Acts", the scope checker said Central only, so the
scope checker refused questions the website promised. The coverage categories now live
in ONE file, core/coverage.json. This test walks the whole repository and FAILS if a
coverage claim (a court name, "Central Acts", "state Acts", "Acts and regulations",
"High Courts", "tribunals" ...) is written as a literal anywhere else.

What is not scanned, and why (each is a boundary, not an oversight):
  * tests/, web/src/__tests__/, web/src/lib/fake/: test fixtures and labelled sample
    data that stand in for records; they assert behaviour, they tell no user anything
  * data/: the data-copy scripts describe the data itself, not the product
  * docs/ (except UX-COPY.md), team/, after-11-weeks/, knowledge/, legal/, .claude/,
    skills-used/, CLAUDE.md: history, plans and instructions that DISCUSS coverage;
    people write them and the product never reads them
The README and docs/UX-COPY.md ARE scanned: their coverage sentence is a generated
block (python -m core.coverage --write-docs), checked below.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from core import coverage
from core.settings import Settings

ROOT = Path(__file__).resolve().parent.parent

SOURCE_FILES = {"core/coverage.json"}
SKIP_PREFIXES = (
    "tests/",
    "web/src/__tests__/",
    "web/src/lib/fake/",
    "data/",
    "docs/",
    "team/",
    "after-11-weeks/",
    "knowledge/",
    "legal/",
    ".claude/",
    "skills-used/",
    "web/public/",
)
SKIP_FILES = {"CLAUDE.md"}
KEEP_DOCS = {"docs/UX-COPY.md"}
SUFFIXES = (".py", ".ts", ".tsx", ".mjs", ".txt", ".md", ".yml", ".yaml", ".sql")

CLAIMS = [
    r"\bcentral\s+(?:and\s+(?:state\s+)?)?acts?\b",
    r"\bstate\s+acts?\b",
    r"\bcentral\s+(?:and|or)\s+state\b",
    r"\bacts\s+and\s+regulations\b",
    r"\ball\s+(?:the\s+)?(?:indian\s+)?acts\b",
    r"\bhigh\s+courts?\b",
    r"\bdistrict\s+courts?\b",
    r"\btribunals?\b",
    r"\bsupreme\s+court\b",
]
CLAIM = re.compile("|".join(CLAIMS), re.IGNORECASE)


def _tracked() -> list[str]:
    out = subprocess.run(  # noqa: S603
        ["git", "ls-files"],  # noqa: S607
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    return out.splitlines()


def _scanned(path: str) -> bool:
    if path in SOURCE_FILES or path in SKIP_FILES:
        return False
    if path in KEEP_DOCS:
        return True
    if path.startswith(SKIP_PREFIXES):
        return False
    return path.endswith(SUFFIXES) and (ROOT / path).is_file()


def _strip_generated(path: str, text: str) -> str:
    """The generated README/UX-COPY blocks are the one place a sentence is allowed to
    appear outside the JSON, because they are produced from it (and checked below)."""
    return re.sub(
        r"<!-- (coverage[\w-]*):begin -->.*?<!-- \1:end -->", "", text, flags=re.S
    )


def test_no_coverage_claim_is_written_outside_the_one_source():
    offenders = []
    for path in _tracked():
        if not _scanned(path):
            continue
        text = _strip_generated(path, (ROOT / path).read_text(encoding="utf-8"))
        for n, line in enumerate(text.splitlines(), 1):
            m = CLAIM.search(line)
            if m:
                offenders.append(f"{path}:{n}: {m.group(0)!r}")
    assert offenders == [], "coverage claims outside core/coverage.json:\n" + "\n".join(
        offenders
    )


def test_the_guard_can_fail(tmp_path):
    """The pattern really catches the sentences that drifted."""
    for s in (
        "Version 1 covers Supreme Court judgments and central and state Acts "
        "and regulations",
        "Needs a High Court judgment or a state-level source. state Acts",
        "v1 serves the Supreme Court and `acts_india` (Central Acts) only.",
        "It does not include High Courts, district courts, tribunals",
    ):
        assert CLAIM.search(s), s


# --- the source itself ------------------------------------------------------------
def test_the_source_loads_and_is_measured_but_the_wording_is_not_approved():
    cov = coverage.load_coverage()
    assert cov.status == "measured"  # written only by data/coverage_report.py
    assert cov.sentence_approved is False  # NEEDS-OWNER: the owner approves the wording
    assert cov.covered_labels  # names something


def test_a_measured_file_must_say_when_and_by_what():
    raw = {
        "status": "measured", "sentence_approved": True,
        "sentence_template": "x {covered}", "not_in_dataset_message": "m",
        "courts": [], "excluded": [], "buckets": {},
        "instruments": [{"id": "i", "covered_label": "L", "payload": {}}],
    }  # fmt: skip
    with pytest.raises(ValueError, match="when and by what"):
        coverage._parse(raw)


def test_a_source_that_names_nothing_is_refused():
    raw = {
        "status": "placeholder", "sentence_approved": False, "sentence_template": "x",
        "not_in_dataset_message": "m", "courts": [], "instruments": [],
        "excluded": [], "buckets": {},
    }  # fmt: skip
    with pytest.raises(ValueError):
        coverage._parse(raw)


def test_every_reader_asks_the_source():
    from adapters import jev

    crit = coverage.scope_criteria()
    assert jev.SCOPE_CRITERIA == crit
    assert set(crit) == {
        "in_scope", "needs_high_court", "needs_tribunal", "after_snapshot",
        "not_in_dataset", "not_legal",
    }  # fmt: skip
    prompt = (ROOT / "core/prompts/decide.txt").read_text()
    assert (
        "{scope_help}" in prompt and "{scope_choices}" in prompt
    )  # filled from the source
    assert coverage.court_payload("supreme_court") == {
        "court": coverage.load_coverage().courts[0].name
    }


def test_the_sentence_names_only_what_the_source_names():
    """If the source lists only one category, the sentence names only that one."""
    cov = coverage.Coverage(
        status="placeholder", sentence_approved=False,
        sentence_template="{product} covers {covered}. Not {excluded}.",
        not_in_dataset_message="m",
        courts=(), instruments=(coverage.Instrument("a", "Alpha Acts", {}),),
        excluded=("beta",), buckets=dict(coverage.load_coverage().buckets),
    )  # fmt: skip
    s = coverage.coverage_sentence("P", cov)
    assert s == "P covers Alpha Acts. Not beta."
    assert "state" not in s.lower() and "central" not in s.lower()


def test_scope_criteria_follow_the_source_not_a_copy():
    cov = coverage.load_coverage()
    changed = coverage.Coverage(
        status=cov.status, sentence_approved=cov.sentence_approved,
        sentence_template=cov.sentence_template,
        not_in_dataset_message=cov.not_in_dataset_message,
        courts=cov.courts,
        instruments=(coverage.Instrument("x", "Zeta Statutes", {}),),
        excluded=cov.excluded, buckets=cov.buckets,
    )  # fmt: skip
    assert "Zeta Statutes" in coverage.scope_criteria(changed)["in_scope"]
    assert "Zeta Statutes" in coverage.scope_question(changed)


# --- README and UX-COPY are generated from it ------------------------------------
def test_readme_and_ux_copy_blocks_match_the_source():
    state = coverage.docs_in_sync(Settings.model_fields["PRODUCT_NAME"].default)
    assert all(state.values()), f"{state}: run `python -m core.coverage --write-docs`"


def test_the_courts_in_the_file_are_named_by_the_snapshot_and_are_only_what_is_served():
    """coverage.json is generated (data/coverage_report.py): every court it lists is one the
    record-id table names, and today that is the Supreme Court alone, because `kanoon_v1`
    serves no High Court (A146). The High Courts return here when they are served."""
    import json

    ids = json.loads((ROOT / "core" / "court_ids.json").read_text())["courts"]
    labels = {c["label"] for c in ids.values()}
    cov = coverage.load_coverage()
    assert {c.payload["court"] for c in cov.courts} <= labels
    assert [c.id for c in cov.courts] == ["supreme_court"]
    assert [i.id for i in cov.instruments] == ["central_acts"]
    assert cov.status == "measured" and cov.measured_at and cov.generated_by


def test_the_checked_in_file_is_what_the_generator_writes():
    import subprocess
    import sys

    r = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "data.coverage_report"], cwd=ROOT, capture_output=True
    )
    assert r.returncode == 0, r.stdout.decode()
