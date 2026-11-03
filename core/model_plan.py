"""Which Voyage model embeds the query, and for which courts (A128). Pipeline step 5 (Search).

Plain words: some collections hold chunks embedded by three different models, by court. A query
vector made with one model matches that model's chunks well and the others only to about 0.95
cosine, so a single query vector under-retrieves the mismatched share (measured: 73% of sampled
chunks if everything is queried with voyage-4, 7.6% if each court is queried with its own
majority model). The fix is to embed the query once per model and search each vector only among
the courts that model built, all in ONE Qdrant call (adapters/qdrant.py).

A collection named in VOYAGE_EMBED_MODELS is single-model: plan_for() returns None and nothing
changes (the served kanoon_v1 is one). Only a collection registered per court in
VOYAGE_COURT_MODELS gets a plan. A court that is not registered is refused, never defaulted.

NO_COURT registers the records that carry no court code (Acts): without it they would be
reachable by keyword search only.
"""

from __future__ import annotations

import collections
from dataclasses import dataclass

from core.settings import Settings

NO_COURT = "NO_COURT"


@dataclass(frozen=True)
class ModelGroup:
    model: str
    codes: tuple[str, ...]  # court codes this model built, sorted
    no_court: bool = False  # also the records with no court code (Acts)

    @property
    def embed_code(self) -> str:
        """A court code to ask the settings for this group's model."""
        return self.codes[0] if self.codes else NO_COURT


def plan_for(settings: Settings, collection: str) -> tuple[ModelGroup, ...] | None:
    """None for a single-model collection (embed once, search everything). Otherwise one
    group per distinct model, largest first, in a stable order."""
    if collection in settings.VOYAGE_EMBED_MODELS:
        return None
    per_court = settings.VOYAGE_COURT_MODELS.get(collection)
    if per_court is None:
        return None  # embed_model_for() refuses an unrecorded collection, as before
    by_model: dict[str, list[str]] = collections.defaultdict(list)
    for code, model in per_court.items():
        by_model[model].append(code)
    groups = [
        ModelGroup(
            model,
            tuple(sorted(c for c in codes if c != NO_COURT)),
            NO_COURT in codes,
        )
        for model, codes in by_model.items()
    ]
    groups.sort(key=lambda g: (-(len(g.codes) + g.no_court), g.model))
    return tuple(groups)


def unregistered(
    settings: Settings, collection: str, present_codes: dict[str, int]
) -> dict[str, int]:
    """Court codes present in `collection` (code -> points) that are NOT registered. Each
    is reachable by keyword search only, so a copy step must see this empty. The empty
    code (no court) is reported under NO_COURT unless that is registered."""
    per_court = settings.VOYAGE_COURT_MODELS.get(collection)
    if per_court is None:
        return {}
    return {
        (NO_COURT if code in ("", None) else code): n
        for code, n in present_codes.items()
        if (NO_COURT if code in ("", None) else code) not in per_court
    }
