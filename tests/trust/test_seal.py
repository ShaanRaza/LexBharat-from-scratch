"""The verifier cannot be skipped: only a sealed answer is accepted."""

import ast
import dataclasses
from pathlib import Path

import pytest

from core import contracts
from core.contracts import Citation, Footer, PipelineResult, VerifiedAnswer
from core.settings import get_settings
from core.verify import seal_answer, verify

ROOT = Path(__file__).resolve().parents[2]


def sealed():
    return seal_answer("Text [S1].", [], [])


def test_sealed_answer_is_accepted():
    assert contracts.is_sealed(sealed())


def test_hand_built_answer_is_rejected():
    assert not contracts.is_sealed(VerifiedAnswer("x", (), ()))


def test_copied_seal_on_other_text_is_rejected():
    a = sealed()
    assert not contracts.is_sealed(dataclasses.replace(a, text="Different [S1]."))


def test_added_citation_after_sealing_is_rejected():
    a = sealed()
    c = Citation("S1", "r", "verified", None, None, None)
    assert not contracts.is_sealed(dataclasses.replace(a, citations=(c,)))


def test_raw_string_and_none_rejected():
    assert not contracts.is_sealed("some text")
    assert not contracts.is_sealed(None)


def test_seal_made_with_a_different_key_is_rejected(monkeypatch):
    a = sealed()
    monkeypatch.setenv("SEAL_KEY", "another-key")
    get_settings.cache_clear()
    assert not contracts.is_sealed(a)


def test_no_key_means_nothing_seals(monkeypatch):
    monkeypatch.setenv("SEAL_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError):
        seal_answer("x", [], [])


def test_answered_result_requires_sealed_answer():
    footer = Footer("2026-08", "v2026.08")
    with pytest.raises(ValueError):
        PipelineResult("answered", VerifiedAnswer("x", (), ()), footer)
    PipelineResult("answered", sealed(), footer)


def test_show_rejects_unsealed_answer():
    show_mod = pytest.importorskip("core.show")
    footer = Footer("2026-08", "v2026.08")
    # PipelineResult itself refuses; bypass it to prove show() has its own guard.
    result = object.__new__(PipelineResult)
    for f in dataclasses.fields(PipelineResult):
        object.__setattr__(
            result, f.name, f.default if f.default is not dataclasses.MISSING else None
        )
    object.__setattr__(result, "outcome", "answered")
    object.__setattr__(result, "answer", VerifiedAnswer("leak [S1]", (), ()))
    object.__setattr__(result, "footer", footer)

    async def drain():
        return [e async for e in show_mod.show(result)]

    import asyncio

    with pytest.raises((TypeError, ValueError)):
        asyncio.run(drain())


def test_only_verify_py_calls_seal_answer():
    offenders = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith((".venv", "tests/", "node_modules", "web/")):
            continue
        if rel == "core/verify.py":
            continue
        try:
            tree = ast.parse(path.read_text(errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
                if name == "seal_answer":
                    offenders.append(rel)
    assert offenders == []


async def test_verify_returns_sealed(world):
    ans = await verify(world.draft("Hello."), world.passages, world.deps)
    assert contracts.is_sealed(ans)
