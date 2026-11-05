"""Which model does the live path ask Voyage for? (A186). A fake HTTP transport records the request;
no vendor is called. Pipeline step 5 (Search): core/search.py embed_query -> adapters/voyage.py."""

import json
from types import SimpleNamespace

import httpx
import pytest

from adapters.voyage import VoyageClient
from core.search import embed_query
from core.settings import Settings, UnknownEmbeddingModel


def _client(settings, seen):
    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        seen.append(body)
        return httpx.Response(
            200,
            json={
                "data": [{"index": 0, "embedding": [0.0] * 1024}],
                "usage": {"total_tokens": 3},
            },
        )

    return VoyageClient(settings, transport=httpx.MockTransport(handler))


async def _ask(collection, models=None):
    kw = {"VOYAGE_EMBED_MODELS": models} if models else {}
    s = Settings(CORPUS_COLLECTION=collection, VOYAGE_API_KEY="fake", **kw)
    seen: list = []
    deps = SimpleNamespace(settings=s, embedder=_client(s, seen))
    await embed_query("what does section 11 of the cpc say", deps)
    return seen


async def test_kanoon_v1_query_is_sent_with_the_model_the_map_names():
    seen = await _ask("kanoon_v1")
    assert [b["model"] for b in seen] == [
        "voyage-4-large"
    ]  # the map, not a fixed voyage-4
    assert seen[0]["input_type"] == "query"


async def test_an_unregistered_new_collection_is_refused_before_any_request():
    with pytest.raises(UnknownEmbeddingModel):
        await _ask(
            "research_v4"
        )  # research_v3 is registered (voyage-4-large) since 5 Nov


async def test_a_registered_new_collection_uses_whatever_the_map_says():
    for model in ("voyage-4", "voyage-4-large"):
        seen = await _ask(
            "research_v3", {"kanoon_v1": "voyage-4-large", "research_v3": model}
        )
        assert [b["model"] for b in seen] == [model]
