"""Conversations and the streaming answer route (pipeline steps 1-11 via the bridge)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from api import bridge
from api import schemas as s
from api.auth import CurrentUser, User
from api.errors import ApiError, request_id_of

router = APIRouter()


@router.post("/conversations", response_model=s.ConversationOut, status_code=201)
async def create_conversation(
    body: s.ConversationCreate, request: Request, user: CurrentUser = User
):
    if body.document_id is not None or body.module == "document":
        if not request.app.state.core_settings.FEATURE_UPLOADS:
            raise ApiError(403, "feature_disabled", "Uploads are not available yet.")
    return await request.app.state.repo.create_conversation(
        user.id, body.module, str(body.document_id) if body.document_id else None
    )


@router.get("/conversations", response_model=s.ConversationList)
async def list_conversations(
    request: Request,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    user: CurrentUser = User,
):
    items, nxt = await request.app.state.repo.list_conversations(user.id, cursor, limit)
    return s.ConversationList(items=items, next_cursor=nxt)


@router.get("/conversations/{conv_id}", response_model=s.ConversationDetail)
async def get_conversation(conv_id: str, request: Request, user: CurrentUser = User):
    conv = await request.app.state.repo.get_conversation(user.id, conv_id)
    if conv is None:
        raise ApiError(404, "not_found", "Conversation not found.")
    prov = await _provenance(request)
    return s.ConversationDetail(**conv, provenance=prov)


async def _provenance(request: Request) -> s.Provenance | None:
    cov = await request.app.state.repo.data_as_of()
    if not cov:
        return None
    cs = request.app.state.core_settings
    return s.Provenance(
        data_as_of=cov[0], snapshot_version=cov[1], credit=cs.DATA_CREDIT
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/conversations/{conv_id}/messages")
async def ask(
    conv_id: str, body: s.MessageCreate, request: Request, user: CurrentUser = User
):
    app = request.app
    repo = app.state.repo
    if await repo.get_conversation(user.id, conv_id) is None:
        raise ApiError(404, "not_found", "Conversation not found.")
    await repo.add_user_message(conv_id, body.content)
    turns, summary = await repo.history(conv_id)
    pipe = app.state.pipeline
    if pipe is None:
        raise ApiError(503, "service_unavailable", "Answers are unavailable right now.")
    req = bridge.build_request(
        user.id, user.plan, conv_id, body.content, turns, summary
    )
    cov = await repo.data_as_of()
    rid = request_id_of(request)

    async def events() -> AsyncIterator[str]:
        async for name, data in bridge.stream_answer(
            req, pipe.run, pipe.stream, cov[0] if cov else "",
            app.state.core_settings.DATA_CREDIT, rid,
        ):  # fmt: skip
            yield _sse(name, data)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Request-ID": rid,
        },
    )


@router.post("/feedback", response_model=s.Ok)
async def feedback(body: s.FeedbackIn, request: Request, user: CurrentUser = User):
    await request.app.state.repo.add_feedback(user.id, body.model_dump(mode="json"))
    return s.Ok()
