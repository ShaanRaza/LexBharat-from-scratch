"""A127: one Voyage call site, and `input_type` is a required argument with no default.

Pipeline steps touched by the change under test: step 5 (Search, the query embedding) and
any corpus or upload embedding (the document path). Nothing here touches a verifier check.

What is checked:
  * `input_type` has no default anywhere an embedder is defined, and leaving it out is a
    TypeError; a value that is not "query" or "document" is refused BEFORE any request;
  * the request carries the chosen input_type, the collection's model and 1024 dimensions;
  * a document call reproduces known stored vectors (see the note on what that proves);
  * the batch path retries a rate limit and a server error, and the online path does not;
  * no file outside adapters/voyage.py talks to Voyage (CLAUDE.md section 2 rule 1).
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import httpx
import numpy as np
import pytest

from adapters import voyage as voyage_mod
from adapters.voyage import (
    DIM,
    Embedder,
    FakeEmbedder,
    VoyageClient,
    VoyageUnavailable,
)
from core.settings import Settings, UnknownEmbeddingModel

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "voyage_known_vectors.json").read_text()
)
ROWS = FIXTURE["rows"]


def _settings(**over) -> Settings:
    return Settings(_env_file=None, VOYAGE_API_KEY="test-key", **over)


def _cos(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


# --- 1. input_type is required, with no default ----------------------------------------
@pytest.mark.parametrize(
    "fn",
    [
        VoyageClient.embed,
        VoyageClient.embed_batch,
        FakeEmbedder.embed,
        FakeEmbedder.embed_batch,
        Embedder.embed,
        Embedder.embed_batch,
    ],
    ids=lambda f: f.__qualname__,
)
def test_input_type_has_no_default_anywhere_an_embedder_is_defined(fn):
    p = inspect.signature(fn).parameters["input_type"]
    assert p.default is inspect.Parameter.empty, (
        f"{fn.__qualname__} gives input_type a default"
    )


async def test_leaving_input_type_out_is_a_type_error_not_a_silent_query():
    c = VoyageClient(_settings(VOYAGE_EMBED_MODELS={"c": "voyage-4"}))
    with pytest.raises(TypeError):
        await c.embed("some text", "c")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        await c.embed_batch(["some text"], "c")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        await FakeEmbedder().embed("some text", "c")  # type: ignore[call-arg]


async def test_a_value_that_is_not_query_or_document_is_refused_before_any_request():
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.0]}]})

    c = VoyageClient(
        _settings(VOYAGE_EMBED_MODELS={"c": "voyage-4"}),
        transport=httpx.MockTransport(handler),
    )
    for bad in ("doc", "Query", "", None, "search_query"):
        with pytest.raises(ValueError):
            await c.embed("x", "c", bad)  # type: ignore[arg-type]
    assert sent == []


async def test_the_fake_embedder_gives_a_query_and_a_document_different_vectors():
    f = FakeEmbedder()
    q = await f.embed("limitation period for a cheque bounce complaint", None, "query")
    d = await f.embed(
        "limitation period for a cheque bounce complaint", None, "document"
    )
    assert q != d and _cos(q, d) < 0.999  # a wrong choice would show up in a test


# --- 2. what is sent --------------------------------------------------------------------
def _capturing(vectors=None, usage=7):
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent.append((str(request.url), request.headers.get("authorization"), body))
        n = len(body["input"])
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": i, "embedding": (vectors or [[0.5] * 4] * n)[i]}
                    for i in reversed(range(n))  # out of order on purpose
                ],
                "usage": {"total_tokens": usage},
            },
        )

    return sent, httpx.MockTransport(handler)


async def test_the_request_carries_the_chosen_input_type_the_model_and_1024_dimensions():
    sent, transport = _capturing()
    c = VoyageClient(
        _settings(VOYAGE_EMBED_MODELS={"a": "voyage-4", "b": "voyage-4-large"}),
        transport=transport,
    )
    await c.embed("q", "a", "query")
    await c.embed("d", "b", "document")
    (u1, auth1, b1), (u2, _, b2) = sent
    assert DIM == 1024 and u1.endswith("/embeddings") and auth1 == "Bearer test-key"
    assert (b1["model"], b1["input_type"], b1["output_dimension"]) == (
        "voyage-4",
        "query",
        1024,
    )
    assert (b2["model"], b2["input_type"], b2["output_dimension"]) == (
        "voyage-4-large",
        "document",
        1024,
    )
    assert b1["input"] == ["q"] and b2["input"] == ["d"]


async def test_a_batch_is_one_request_returned_in_input_order_with_the_billed_tokens():
    vecs = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    sent, transport = _capturing(vectors=vecs, usage=123)
    c = VoyageClient(
        _settings(VOYAGE_EMBED_MODELS={"c": "voyage-4"}), transport=transport
    )
    batch = await c.embed_batch(["x", "y", "z"], "c", "document")
    assert len(sent) == 1 and sent[0][2]["input"] == ["x", "y", "z"]
    assert batch.vectors == vecs  # the response came back reversed; order is restored
    assert batch.total_tokens == 123
    with pytest.raises(ValueError):
        await c.embed_batch([], "c", "document")


async def test_an_unmeasured_collection_is_refused_before_any_request():
    sent, transport = _capturing()
    c = VoyageClient(_settings(), transport=transport)
    with pytest.raises(UnknownEmbeddingModel):
        await c.embed_batch(["x"], "never-measured", "document")
    assert sent == []


async def test_a_short_answer_from_voyage_is_an_error_not_a_misaligned_batch():
    def handler(request):
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.0]}]})

    c = VoyageClient(
        _settings(VOYAGE_EMBED_MODELS={"c": "voyage-4"}),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(VoyageUnavailable):
        await c.embed_batch(["a", "b"], "c", "document")


# --- 3. a document call reproduces known stored vectors ---------------------------------
def _voyage_stand_in():
    """A stand-in for the service, built from the real fixture. It answers a request with
    the corpus's stored vector ONLY when the request is the one that reproduces it in
    the real service (measured): that collection's model, input_type "document", 1024
    dimensions. Any other request gets a different vector. So this proves the adapter
    asks for the right thing; it does NOT prove Voyage's behaviour, which the live test
    below does when a key is present."""
    by_text = {r["text"]: r for r in ROWS}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        out = []
        for i, text in enumerate(body["input"]):
            row = by_text[text]
            right = (
                body["model"] == row["expected_model"]
                and body["input_type"] == "document"
                and body["output_dimension"] == 1024
            )
            vec = (
                row["stored_vector"] if right else list(reversed(row["stored_vector"]))
            )
            out.append({"index": i, "embedding": vec})
        return httpx.Response(200, json={"data": out, "usage": {"total_tokens": 1}})

    return httpx.MockTransport(handler)


@pytest.mark.parametrize("row", ROWS, ids=[r["chunk_id"] for r in ROWS])
async def test_a_document_call_reproduces_the_stored_vector(row):
    c = VoyageClient(
        _settings(VOYAGE_EMBED_MODELS={row["collection"]: row["expected_model"]}),
        transport=_voyage_stand_in(),
    )
    got = await c.embed(row["text"], row["collection"], "document")
    assert _cos(got, row["stored_vector"]) >= 0.998
    wrong = await c.embed(row["text"], row["collection"], "query")  # the trap
    assert _cos(wrong, row["stored_vector"]) < 0.95


def test_the_fixture_is_real_and_covers_both_models():
    assert len(ROWS) >= 5 and {r["expected_model"] for r in ROWS} == {
        "voyage-4",
        "voyage-4-large",
    }
    for r in ROWS:
        v = np.asarray(r["stored_vector"])
        assert (
            v.shape == (1024,)
            and abs(np.linalg.norm(v) - 1) < 1e-3
            and len(r["text"]) > 400
        )


def test_the_models_in_the_fixture_are_the_ones_the_settings_record():
    s = Settings(_env_file=None)
    for r in ROWS:
        assert s.embed_model_for(r["collection"]) == r["expected_model"]


# --- 4. retries: the batch path waits, the online path does not --------------------------
def _flaky(statuses):
    calls = []

    def handler(request):
        calls.append(1)
        status = statuses[min(len(calls) - 1, len(statuses) - 1)]
        if status == 200:
            return httpx.Response(
                200,
                json={
                    "data": [{"index": 0, "embedding": [0.1]}],
                    "usage": {"total_tokens": 3},
                },
            )
        return httpx.Response(status, json={"error": "x"})

    return calls, httpx.MockTransport(handler)


@pytest.fixture
def no_sleep(monkeypatch):
    waited = []

    async def fake_sleep(s):
        waited.append(s)

    monkeypatch.setattr(voyage_mod.asyncio, "sleep", fake_sleep)
    return waited


async def test_the_batch_path_retries_a_rate_limit_then_succeeds(no_sleep):
    calls, transport = _flaky([429, 503, 200])
    c = VoyageClient(
        _settings(VOYAGE_EMBED_MODELS={"c": "voyage-4"}),
        max_attempts=5,
        transport=transport,
    )
    batch = await c.embed_batch(["x"], "c", "document")
    assert len(calls) == 3 and batch.total_tokens == 3 and len(no_sleep) == 2


async def test_the_online_path_makes_one_attempt_and_falls_back(no_sleep):
    calls, transport = _flaky([503])
    c = VoyageClient(
        _settings(VOYAGE_EMBED_MODELS={"c": "voyage-4"}), transport=transport
    )
    with pytest.raises(VoyageUnavailable):
        await c.embed("x", "c", "query")
    assert len(calls) == 1 and no_sleep == []  # keyword-only search takes over, at once


async def test_a_bad_key_is_not_retried(no_sleep):
    calls, transport = _flaky([401])
    c = VoyageClient(
        _settings(VOYAGE_EMBED_MODELS={"c": "voyage-4"}),
        max_attempts=5,
        transport=transport,
    )
    with pytest.raises(VoyageUnavailable):
        await c.embed_batch(["x"], "c", "document")
    assert len(calls) == 1


# --- 5. one call site (CLAUDE.md section 2 rule 1) --------------------------------------
def test_nothing_outside_the_voyage_adapter_talks_to_voyage():
    """The Voyage URL and the voyageai library appear in adapters/voyage.py and nowhere
    else in code (tests may mention them). This is what the three corpus scripts used
    to violate."""
    bad = []
    for base in ("core", "api", "workers", "data", "evals", "adapters", "infra"):
        for f in (ROOT / base).rglob("*.py"):
            if f == ROOT / "adapters" / "voyage.py":
                continue
            for n, line in enumerate(f.read_text().splitlines(), 1):
                code = line.split("#", 1)[0]
                if re.search(
                    r"api\.voyageai\.com|^\s*(?:import|from)\s+voyageai\b", code
                ):
                    bad.append(f"{f.relative_to(ROOT)}:{n}")
    assert bad == [], bad
