"""Adapters: Jev with the Gemini fallback, fakes, webhook signature, vendor boundary."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import pytest

from adapters.decisions import (
    DecisionUnavailable,
    FakeDecisions,
    FallbackDecisions,
    GeminiDecider,
)
from adapters.llm import FakeLLM
from adapters.razorpay import BadSignature, FakePayments
from adapters.s3 import FakeFileStore, object_key
from core.contracts import Passage
from core.settings import Settings

ROOT = Path(__file__).resolve().parents[2]


def settings_with(**kw) -> Settings:
    return Settings(JEV_TIMEOUT_MS=50, **kw)


def passage(kind="judgment", text="bail granted for economic offences"):
    return Passage(record_id="r1", text=text, kind=kind)


class SpyJev(FakeDecisions):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.calls = 0

    async def rate_passage(self, query, passage):
        self.calls += 1
        return await super().rate_passage(query, passage)

    async def decide(self, query, *, uploads=False):
        self.calls += 1
        return await super().decide(query, uploads=uploads)


def rate_json(rating="answers", score=0.9):
    return json.dumps({"rating": rating, "score": score})


def gemini(text):
    s = Settings()
    return GeminiDecider(FakeLLM(text), s)


async def test_jev_used_when_enabled_and_healthy():
    jev = SpyJev()
    d = FallbackDecisions(
        jev,
        gemini(rate_json("not_relevant", 0.0)),
        settings_with(JEV_ENABLED_GATE=True),
    )
    r, _ = await d.rate_passage("bail economic offences", passage())
    assert jev.calls == 1 and r != "not_relevant"


async def test_gemini_used_when_jev_switched_off():
    jev = SpyJev()
    d = FallbackDecisions(jev, gemini(rate_json("partly", 0.7)), settings_with())
    assert await d.rate_passage("q", passage()) == ("partly", 0.7)
    assert jev.calls == 0


async def test_gemini_fallback_when_jev_is_slower_than_timeout():
    jev = SpyJev(delay_s=0.5)
    d = FallbackDecisions(
        jev, gemini(rate_json("answers", 0.8)), settings_with(JEV_ENABLED_GATE=True)
    )
    assert await asyncio.wait_for(d.rate_passage("q", passage()), 2) == ("answers", 0.8)


async def test_gemini_fallback_when_jev_down():
    d = FallbackDecisions(
        SpyJev(down=True), gemini(rate_json()), settings_with(JEV_ENABLED_GATE=True)
    )
    assert (await d.rate_passage("q", passage()))[0] == "answers"


async def test_upload_text_never_reaches_jev():
    jev = SpyJev()
    s = settings_with(
        JEV_ENABLED_GATE=True,
        JEV_ENABLED_CLAIM=True,
        JEV_ENABLED_SCOPE=True,
        JEV_ENABLED_FILTERS=True,
        JEV_ENABLED_SAFETY=True,
    )
    fb = GeminiDecider(FakeLLM(lambda p, s_: "supports"), s)
    d = FallbackDecisions(jev, fb, s)
    up = passage("upload", "my client's secret facts")
    assert await d.claim_support("sentence", up) == "supports"
    fb2 = GeminiDecider(FakeLLM(rate_json()), s)
    d2 = FallbackDecisions(jev, fb2, s)
    await d2.rate_passage("q", up)
    assert jev.calls == 0
    scope = json.dumps({"scope": "in_scope", "safety": "normal"})
    d3 = FallbackDecisions(jev, GeminiDecider(FakeLLM(scope), s), s)
    await d3.decide("question in an upload chat", uploads=True)
    assert jev.calls == 0
    await d3.decide("plain question")
    assert jev.calls == 1  # sanity: without the flag Jev IS used


async def test_both_down_raises_decision_unavailable():
    d = FallbackDecisions(
        SpyJev(down=True),
        GeminiDecider(FakeLLM(down=True), Settings()),
        settings_with(JEV_ENABLED_GATE=True),
    )
    with pytest.raises(DecisionUnavailable):
        await d.rate_passage("q", passage())


@pytest.mark.parametrize("bad", ["maybe", "supports it", ""])
async def test_choice_outside_allowed_list_is_an_error_not_a_guess(bad):
    with pytest.raises(DecisionUnavailable):
        await gemini(bad).claim_support("s", passage())


def test_razorpay_signature_checked():
    p = FakePayments("s3cret")
    body = b'{"event": "subscription.charged", "payload": {}}'
    assert p.verify_webhook(body, p.sign(body)).event == "subscription.charged"
    with pytest.raises(BadSignature):
        p.verify_webhook(body, "deadbeef")
    with pytest.raises(BadSignature):
        p.verify_webhook(body + b" ", p.sign(body))


async def test_s3_keys_are_per_user():
    assert object_key("u1", "d1") == "uploads/u1/d1"
    with pytest.raises(ValueError):
        object_key("u1/../u2", "d1")
    fs = FakeFileStore()
    fs.put("u1", "d1", b"x")
    assert not await fs.exists("u2", "d1")
    await fs.delete("u1", "d1")
    assert not await fs.exists("u1", "d1")


def test_fakes_refused_in_production(monkeypatch):
    from adapters.voyage import FakeEmbedder
    from core.settings import get_settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SEAL_KEY", "k")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError):
        FakeEmbedder()


def test_production_without_seal_key_refuses_to_start():
    with pytest.raises(ValueError):
        Settings(ENVIRONMENT="production", SEAL_KEY="")


VENDORS = {
    "litellm": "llm.py",
    "qdrant_client": "qdrant.py",
    "boto3": "s3.py",
    "fitz": "ocr.py",
    "firebase_admin": "firebase.py",
    "voyageai": "voyage.py",
    "razorpay": "razorpay.py",
    "redis": "cache.py",
    "httpx": "voyage.py",
}


def test_vendor_libraries_imported_only_in_their_adapter():
    bad = []
    for base in ("core", "api", "workers", "data", "adapters"):
        for f in (ROOT / base).rglob("*.py"):
            for line in f.read_text().splitlines():
                m = re.match(r"\s*(?:import|from)\s+([A-Za-z_]+)", line)
                if m and m.group(1) in VENDORS:
                    ok = base == "adapters" and f.name == VENDORS[m.group(1)]
                    if not ok and base != "workers" and base != "data":
                        bad.append((str(f.relative_to(ROOT)), m.group(1)))
    assert bad == [], bad


def test_pipeline_module_imports_no_adapter():
    src = (ROOT / "core" / "pipeline.py").read_text().splitlines()
    bad = [line for line in src if re.match(r"\s*(from|import)\s+adapters\b", line)]
    assert bad == []
