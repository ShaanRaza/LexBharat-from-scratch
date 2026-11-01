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
    pipe = app.state.pipeline
    if pipe is None:  # check first so a 503 does not store the user's message
        raise ApiError(503, "service_unavailable", "Answers are unavailable right now.")
    conv = await repo.get_conversation(user.id, conv_id)
    if conv is None:
        raise ApiError(404, "not_found", "Conversation not found.")
    if conv.get("document_id"):  # upload chat is not wired to core yet
        raise ApiError(403, "feature_disabled", "Uploads are not available yet.")
    qid = await repo.add_user_message(user.id, conv_id, body.content)
    if qid is None:
        raise ApiError(404, "not_found", "Conversation not found.")
    turns, summary = await repo.history(user.id, conv_id, qid)
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


@router.post(
    "/conversations/{conv_id}/messages/{msg_id}/followups",
    response_model=s.FollowupsOut,
)
async def followups(
    conv_id: str, msg_id: str, request: Request, user: CurrentUser = User
):
    """Next-question suggestions for a SAVED answer (so it was already verified).
    Questions only; the user running one is an ordinary new question."""
    pipe = request.app.state.pipeline
    if pipe is None:
        raise ApiError(503, "service_unavailable", "Suggestions are unavailable.")
    conv = await request.app.state.repo.get_conversation(
        user.id, conv_id
    )  # user-filtered
    if conv is None:
        raise ApiError(404, "not_found", "Conversation not found.")
    msgs = conv["messages"]
    idx = next((i for i, m in enumerate(msgs) if str(m["id"]) == msg_id), None)
    if idx is None or msgs[idx]["role"] != "assistant":
        raise ApiError(404, "not_found", "Answer not found.")
    question = next(
        (m["content"] for m in reversed(msgs[:idx]) if m["role"] == "user"), ""
    )
    try:
        suggestions = await pipe.followups(question, msgs[idx]["content"])
    except Exception:  # noqa: BLE001 (optional feature: never fail, never echo)
        suggestions = []
    return s.FollowupsOut(suggestions=suggestions[:3])


@router.post("/prompts/improve", response_model=s.ImproveOut)
async def improve_question(
    body: s.ImproveIn, request: Request, user: CurrentUser = User
):
    """ "Improve my question": editable text for the input box. Not a pipeline step and
    never a citation (core/improve.py)."""
    pipe = request.app.state.pipeline
    if pipe is None:
        raise ApiError(503, "service_unavailable", "The helper is unavailable.")
    try:
        out = await pipe.improve(body.text)
    except Exception:  # noqa: BLE001 (the helper is optional: keep the user's text)
        return s.ImproveOut(text=body.text, changed=False)
    return s.ImproveOut(text=out.text, changed=out.changed)
