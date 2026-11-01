"""Research chat: create, list, read, and ask (streaming).

Pipeline steps touched: this file only sits around step 10 (Show) and step 11 (Save);
steps 1-9 run inside the pipeline in core/ (see api/pipeline.py).
"""

import logging
import re
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from api import notices
from api.deps import (
    CurrentUser,
    current_user,
    month_start,
    pipeline_dep,
    plan_limit,
    settings_dep,
    store_dep,
)
from api.errors import ApiError, error_body, request_id_var
from api.pagination import DEFAULT_LIMIT, MAX_LIMIT, decode_cursor, encode_cursor
from api.pipeline import FinalAnswer, HistoryTurn, ResearchPipeline, TextDelta
from api.routes.me import limit_headers
from api.schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationList,
    ConversationOut,
    MessageCreate,
)
from api.sse import SourceMarkerFilter, event
from api.store import Store
from core.settings import Settings

log = logging.getLogger("api.chat")
router = APIRouter(tags=["conversations"])

# "Remember" (step 1): the last 6 turns in full = 12 messages, plus the rolling summary.
HISTORY_MESSAGES = 12


@router.post(
    "/conversations",
    response_model=ConversationOut,
    status_code=201,
    summary="Start a conversation",
)
async def create_conversation(
    *,
    body: ConversationCreate,
    user: Annotated[CurrentUser, Depends(current_user)],
    store: Annotated[Store, Depends(store_dep)],
):
    return await store.create_conversation(
        user.id, body.module, body.title, body.document_id
    )


@router.get("/conversations", response_model=ConversationList, summary="List (cursor)")
async def list_conversations(
    *,
    cursor: str | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    user: Annotated[CurrentUser, Depends(current_user)],
    store: Annotated[Store, Depends(store_dep)],
):
    # Ask for one extra row: if it exists there is a next page.
    rows = await store.list_conversations(user.id, decode_cursor(cursor), limit + 1)
    more = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": rows,
        "next_cursor": encode_cursor(rows[-1]["created_at"], rows[-1]["id"])
        if more
        else None,
    }


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetail,
    summary="Full history with sources",
)
async def get_conversation(
    *,
    conversation_id: UUID,
    user: Annotated[CurrentUser, Depends(current_user)],
    store: Annotated[Store, Depends(store_dep)],
    settings: Annotated[Settings, Depends(settings_dep)],
):
    conv = await store.get_conversation(user.id, conversation_id)
    if conv is None:
        # 404 (not 403) so nobody can probe which chat IDs exist.
        raise ApiError(404, "not_found", "Conversation not found.")
    messages = await store.list_messages(conversation_id)
    for m in messages:
        for s in m["sources"]:
            s["citation_label"] = (
                notices.CITATION_AS_RECORDED if s.get("citation") else None
            )
    return {
        **conv,
        "messages": messages,
        "provenance": notices.provenance(settings, await store.data_as_of(None)),
    }


def _words(text: str) -> list[str]:
    """Split into words, keeping the trailing space on each, for word-by-word streaming."""
    return re.findall(r"\S+\s*", text)


@router.post(
    "/conversations/{conversation_id}/messages",
    summary="Ask a question; the answer streams (SSE)",
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def post_message(
    *,
    conversation_id: UUID,
    body: MessageCreate,
    user: Annotated[CurrentUser, Depends(current_user)],
    store: Annotated[Store, Depends(store_dep)],
    pipeline: Annotated[ResearchPipeline, Depends(pipeline_dep)],
    settings: Annotated[Settings, Depends(settings_dep)],
):
    conv = await store.get_conversation(user.id, conversation_id)
    if conv is None:
        raise ApiError(404, "not_found", "Conversation not found.")

    # The usage check runs BEFORE any AI call and stops at the limit with a clear
    # message instead of quietly giving worse answers (docs/API.md).
    limit = plan_limit(settings, user.plan)
    used = await store.answers_used(user.id, month_start())
    headers = limit_headers(limit, used)
    if limit is not None and used >= limit:
        raise ApiError(
            429,
            "quota_exceeded",
            f"You have used all {limit} research answers for this month.",
            headers=headers,
        )

    history_rows = (await store.list_messages(conversation_id))[-HISTORY_MESSAGES:]
    history = [HistoryTurn(m["role"], m["content"]) for m in history_rows]
    events = pipeline.answer(
        user_id=str(user.id),
        question=body.content,
        history=history,
        rolling_summary=conv.get("rolling_summary"),
    )
    # Pull the first event now, so a problem that happens before anything is written
    # (pipeline down, say) becomes a proper HTTP error, not a broken stream.
    try:
        first = await anext(events)
    except StopAsyncIteration:
        first = None

    async def stream() -> AsyncIterator[bytes]:
        marker_filter = SourceMarkerFilter()
        final: FinalAnswer | None = None
        streamed_text = False
        try:
            pending = [first] if first is not None else []
            while True:
                item = pending.pop() if pending else await anext(events, None)
                if item is None:
                    break
                if isinstance(item, TextDelta):
                    out = marker_filter.feed(item.text)
                    if out:
                        streamed_text = True
                        yield event("token", {"text": out})
                elif isinstance(item, FinalAnswer):
                    final = item
                    break
            tail = marker_filter.flush()
            if tail:
                streamed_text = True
                yield event("token", {"text": tail})
            if final is None:
                raise ApiError(502, "pipeline_incomplete", "The answer did not finish.")

            # Cache hits and "not found" replies arrive with no streamed text: send the
            # finished text word by word so the website handles every case the same way.
            if not streamed_text and final.text:
                clean = SourceMarkerFilter()
                for w in _words(final.text):
                    piece = clean.feed(w)
                    if piece:
                        yield event("token", {"text": piece})
                rest = clean.flush()
                if rest:
                    yield event("token", {"text": rest})

            # Step 10 (Show): the ONE citations event, only now, after verification.
            n_removed = len(final.removed)
            note = None
            if n_removed:
                note = (
                    notices.UNVERIFIED_ONE
                    if n_removed == 1
                    else notices.UNVERIFIED_MANY.format(n=n_removed)
                )
            yield event(
                "citations",
                {
                    "citations": [
                        {
                            "source_id": c.source_id,
                            "record_id": c.record_id,
                            "title": c.title,
                            "citation": c.citation,
                            "citation_label": notices.CITATION_AS_RECORDED
                            if c.citation
                            else None,
                            "url": c.url,
                            "status": c.status,
                            "status_label": notices.VERIFICATION_LABEL
                            if c.status == "verified"
                            else notices.PARTLY_SUPPORTED_LABEL,
                        }
                        for c in final.citations
                    ],
                    "removed_count": n_removed,
                    "unverified_note": note,
                    "outcome": final.outcome,
                    "provenance": notices.provenance(settings, final.data_as_of),
                },
            )

            # Step 11 (Save). A cache hit is free and does not count against the limit;
            # neither does a "not found" (nothing was written).
            counted = final.outcome == "answered" and not final.from_cache
            message_id = await store.save_exchange(
                user.id, conversation_id, body.content, final, count_usage=counted
            )
            done = {"message_id": str(message_id), "request_id": request_id_var.get()}
            if limit is not None:
                done["answers_left"] = max(limit - used - (1 if counted else 0), 0)
            yield event("done", done)
        except ApiError as exc:
            yield event("error", error_body(exc.code, exc.message))
        except Exception:
            # Never leak internals into the stream; the traceback goes to the log.
            log.exception("chat stream failed")
            yield event(
                "error",
                error_body("internal_error", "Something went wrong on our side."),
            )

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            **headers,
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",  # tells nginx/Caddy not to hold the stream back
        },
    )
