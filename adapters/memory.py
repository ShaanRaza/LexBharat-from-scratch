"""In-memory fakes for things the platform lane implements for real (PostgreSQL):
usage meter, conversation store, invented_citation_log writer."""

from __future__ import annotations

from collections.abc import Sequence

from core.contracts import PipelineRequest, PipelineResult, RemovedCitation


class FakeUsageMeter:
    def __init__(self, limit: int | None = None):
        self.limit, self.counts = limit, {}

    async def allowed(self, user_id: str, plan: str) -> bool:
        return self.limit is None or self.counts.get(user_id, 0) < self.limit

    async def count_one(self, user_id: str) -> None:
        self.counts[user_id] = self.counts.get(user_id, 0) + 1


class FakeStore:
    def __init__(self) -> None:
        self.saved: list[tuple[PipelineRequest, PipelineResult]] = []

    async def save(self, request: PipelineRequest, result: PipelineResult) -> None:
        self.saved.append((request, result))


class FakeCitationLog:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, RemovedCitation]] = []

    async def write(
        self, question: str, model: str, removed: Sequence[RemovedCitation]
    ) -> None:
        self.rows.extend((question, model, r) for r in removed)
