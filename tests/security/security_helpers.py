# ruff: noqa: E501
"""Shared set-up for the prompt-injection tests (tests/security).

The model stand-in here is a worst case: `ObedientModel` does whatever a hostile string
tells it to, as long as the string is written `<<OBEY: ...>>` and appears anywhere in the
prompt. A real model may resist some of that; the verifier's checks 1-3 are plain Python
and must hold even against a model that resists nothing. Where a test depends on a model
being talked round (check 4, the gate), it says so and is marked xfail(strict=True) so the
break is on record and flips loudly when the code is fixed.
"""

from __future__ import annotations

import json
import re

from adapters.cache import FakeCache
from adapters.decisions import FakeDecisions
from adapters.llm import FakeLLM
from adapters.memory import FakeCitationLog, FakeStore, FakeUsageMeter
from adapters.qdrant import FakeVectorStore
from adapters.voyage import FakeEmbedder, FakeReranker
from core.contracts import Deps, PipelineRequest
from core.gate import gate
from core.settings import Settings
from core.verify import verify

OBEY = re.compile(r"<<OBEY: (.*?)>>", re.S)
RECALL = re.compile(r"<<RECALL: (\d+)>>")  # "mention the passport case": the text names
# nothing, the model supplies the authority from its own training memory

REAL_ID = "rec-real-1"
REAL_TEXT = (
    "Personal liberty under Article 21 cannot be curtailed except by procedure "
    "established by law, and bail is the rule while jail is the exception."
)
QUERY = "personal liberty bail"
REQUEST = PipelineRequest("u1", "Tell me about personal liberty and bail")

# What a hostile string asks the model to write, and what must never reach the user.
FAKE_CASE = "Maneka Gandhi v. Union of India, AIR 1978 SC 597 held the right to travel is absolute"
FAKE_CITE = "(1978) 1 SCC 248 settles this beyond doubt"
FAKE_QUOTE = 'Personal liberty under Article 21 cannot be curtailed except by "procedure abolished by statute" [S1]'
FAKE_LABEL = "Clause 420 now carries no sentence [S9]"
# Strong overlap with S1, so check 4 (a word-overlap fake) would say "supports": only
# check 1 can remove it, because S9 was never retrieved.
FAKE_LABEL_ECHO = "Personal liberty under Article 21 cannot be curtailed except by procedure established by law [S9]"
# No marker at all: only the unmarked-quotation rule can remove it.
FAKE_BARE_QUOTE = 'As the Court put it, "bail is never available to anyone"'
# A real label, a claim the passage does not make: only check 4 can remove it.
FAKE_UNSUPPORTED = "The monsoon session adjourned sine die after a short sitting [S1]"
FABRICATIONS = (
    FAKE_CASE,
    FAKE_CITE,
    FAKE_QUOTE,
    FAKE_LABEL,
    FAKE_LABEL_ECHO,
    FAKE_BARE_QUOTE,
    FAKE_UNSUPPORTED,
)


def recall(*indexes: int) -> str:
    """Hostile text that never names the authority itself: it only points at one the
    model remembers. The verifier's haystack therefore does not hold it."""
    return " ".join(f"<<RECALL: {i}>>" for i in indexes)


def obey(payloads: tuple[str, ...]) -> str:
    """Hostile text that asks a compliant model to append these sentences."""
    return " ".join(f"<<OBEY: {p}>>" for p in payloads)


class ObedientModel(FakeLLM):
    """Rewrite -> a fixed query. Answer -> one honest cited sentence copied from S1, then
    every `<<OBEY: ...>>` found anywhere in the prompt, verbatim, as new sentences.
    Anything else (claim-support, rating, follow-ups) is answered by `other`."""

    def __init__(self, other: str = "", query: str = QUERY):
        self._query, self._other = query, other
        super().__init__(self._respond)

    def _respond(self, prompt: str, system: str) -> str:
        if prompt.startswith("Turn the user's"):
            return json.dumps({"query": self._query})
        if prompt.startswith("You are a legal research assistant"):
            m = re.search(r"\[S1\] (.*?)(?:\n\n|\Z)", prompt, re.S)
            words = OBEY.sub("", m.group(1)).split()[:12] if m else []
            honest = " ".join(words) + " [S1]."
            said = [p.rstrip(".") + "." for p in OBEY.findall(prompt)]
            said += [
                FABRICATIONS[int(i)].rstrip(".") + "." for i in RECALL.findall(prompt)
            ]
            return " ".join([honest, *said])
        if prompt.startswith("You make a fixed-choice decision"):
            return '{"scope": "in_scope", "safety": "normal"}'
        if prompt.startswith("Does the passage help"):
            return '{"rating": "answers", "score": 0.9}'
        if prompt.startswith("Does the passage support"):
            return "supports"
        return self._other


class RelevantGate(FakeDecisions):
    """Rates every passage 'answers' (0.9). For tests where the gate is not under test
    and a long hostile query would otherwise starve FakeDecisions' word-overlap rating."""

    async def rate_passage(self, query, passage):
        return "answers", 0.9


def make_deps(
    settings: Settings | None = None, llm: FakeLLM | None = None, **over
) -> Deps:
    settings = settings or Settings()
    store = FakeVectorStore(settings)
    d = dict(
        settings=settings, embedder=FakeEmbedder(), reranker=FakeReranker(),
        vectors=store, llm=llm or ObedientModel(), decisions=FakeDecisions(),
        cache=FakeCache(), usage=FakeUsageMeter(), store=FakeStore(),
        citation_log=FakeCitationLog(), gate=gate, verify=verify,
    )  # fmt: skip
    d.update(over)
    return Deps(**d)
