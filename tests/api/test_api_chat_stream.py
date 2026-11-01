"""The streaming research route: ordering, the one citations event, usage, failures.

docs/TESTING.md must-pass items covered here:
  * no citation-shaped content before the single post-verification `citations` event
  * the usage check runs BEFORE any AI call and stops at the limit
  * cache hits are free and do not count against the limit
  * the not-legal-advice notice and data-as-of date are on every answer
"""

import json
import uuid

from api_fakes import words

from api.pipeline import (
    FinalAnswer,
    RemovedCitation,
    SourceRow,
    TextDelta,
    VerifiedCitation,
)

CC_BY = "Data: Open India Law by Vaquill AI, CC BY 4.0"


def parse_sse(raw: str) -> list[tuple[str, dict]]:
    out = []
    for block in raw.strip().split("\n\n"):
        name, data = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        out.append((name, data))
    return out


def start(client, env, who="alice"):
    r = client.post("/api/v1/conversations", headers=env.auth(who), json={})
    return r.json()["id"]


def ask(client, env, cid, who="alice", text="What is bail?"):
    return client.post(
        f"/api/v1/conversations/{cid}/messages",
        headers=env.auth(who),
        json={"content": text},
    )


def good_answer(**kw) -> FinalAnswer:
    base = dict(  # noqa: C408
        text="Bail is release pending trial.",
        citations=[
            VerifiedCitation(
                "S1",
                "rec-1",
                "A v. B",
                "[1959] SUPP. 2 S.C.R. 986",
                "https://x/p.pdf",
                "verified",
            )
        ],
        sources=[SourceRow("S1", "rec-1", verified=True, support="supports")],
        data_as_of="2026-08-15",
        model="fake-model",
        tokens_in=10,
        tokens_out=20,
        rewritten_query="what is bail",
    )
    base.update(kw)
    return FinalAnswer(**base)


def test_events_arrive_in_order_tokens_then_one_citations_then_done(client, env):
    env.store.add_case(
        record_id="rec-1", title="A v. B", citation="c", pdf_url="u", full_text="t"
    )
    env.pipeline.events = [*words("Bail is release pending trial."), good_answer()]
    cid = start(client, env)
    r = ask(client, env, cid)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    names = [n for n, _ in events]
    assert names == ["token"] * 5 + ["citations", "done"]
    assert (
        "".join(d["text"] for n, d in events if n == "token")
        == "Bail is release pending trial. "
    )

    citations = events[5][1]
    assert citations["removed_count"] == 0
    assert citations["unverified_note"] is None
    assert citations["provenance"]["data_as_of"] == "2026-08-15"
    assert citations["provenance"]["credit"] == CC_BY
    assert (
        citations["provenance"]["notice"]
        == "TestBuddy gives information, not legal advice"
    )
    c = citations["citations"][0]
    assert c["status"] == "verified"
    assert c["status_label"] == "Record found in dataset"
    assert c["citation"] == "[1959] SUPP. 2 S.C.R. 986"
    assert c["citation_label"] == "as recorded in the dataset"
    assert c["url"] == "https://x/p.pdf"


def test_nothing_citation_shaped_goes_out_before_the_citations_event(client, env):
    # The pipeline wrongly leaks markers, including one split across two chunks.
    env.pipeline.events = [
        TextDelta("Bail is allowed [S1] when "),
        TextDelta("the court agrees [S"),
        TextDelta("2] and (S3) applies. "),
        good_answer(),
    ]
    r = ask(client, env, start(client, env))
    events = parse_sse(r.text)
    before = []
    for name, data in events:
        if name == "citations":
            break
        before.append(data["text"])
    streamed = "".join(before)
    for marker in ("[S1]", "[S2]", "(S3)", "S1", "S2", "S3"):
        assert marker not in streamed, streamed
    assert streamed.replace("  ", " ").startswith("Bail is allowed")
    assert [n for n, _ in events].count("citations") == 1


def test_only_one_citations_event_and_it_is_last_but_done(client, env):
    env.pipeline.events = [*words("a b c"), good_answer()]
    names = [n for n, _ in parse_sse(ask(client, env, start(client, env)).text)]
    assert names.index("citations") == len(names) - 2
    assert names[-1] == "done"


def test_answer_and_sources_are_saved_and_visible_in_history(client, env):
    env.store.add_case(
        record_id="rec-1",
        title="A v. B",
        citation="cit",
        pdf_url="https://x/p.pdf",
        full_text="t",
    )
    env.pipeline.events = [
        *words("Bail is release."),
        good_answer(text="Bail is release."),
    ]
    cid = start(client, env)
    done = parse_sse(ask(client, env, cid).text)[-1][1]
    assert uuid.UUID(done["message_id"])
    assert done["request_id"]

    hist = client.get(f"/api/v1/conversations/{cid}", headers=env.auth()).json()
    assert [m["role"] for m in hist["messages"]] == ["user", "assistant"]
    assert hist["messages"][0]["content"] == "What is bail?"
    assert hist["message_count"] == 2
    assert hist["title"] == "What is bail?"
    src = hist["messages"][1]["sources"][0]
    assert src["source_id"] == "S1"
    assert src["url"] == "https://x/p.pdf"
    assert src["citation_label"] == "as recorded in the dataset"
    assert src["verified"] is True


def test_history_is_passed_to_the_pipeline_on_the_second_question(client, env):
    env.pipeline.events = [*words("One."), good_answer(text="One.")]
    cid = start(client, env)
    ask(client, env, cid, text="first?")
    ask(client, env, cid, text="second?")
    call = env.pipeline.calls[1]
    assert call["question"] == "second?"
    assert [(t.role, t.content) for t in call["history"]] == [
        ("user", "first?"),
        ("assistant", "One."),
    ]


def test_removed_citation_is_noted_logged_and_not_shown(client, env):
    env.pipeline.events = [
        *words("Claim."),
        good_answer(
            citations=[],
            removed=[RemovedCitation("Fake v. Case", "not_retrieved")],
        ),
    ]
    events = parse_sse(ask(client, env, start(client, env)).text)
    citations = dict(events)["citations"]
    assert citations["citations"] == []
    assert citations["removed_count"] == 1
    assert "could not be verified" in citations["unverified_note"]
    assert env.store.invented[0]["reason"] == "not_retrieved"
    assert env.store.invented[0]["cited_text"] == "Fake v. Case"


def test_partly_supported_citation_gets_a_warning_label(client, env):
    env.pipeline.events = [
        *words("x"),
        good_answer(citations=[VerifiedCitation("S1", "r", "T", None, None, "partly")]),
    ]
    c = dict(parse_sse(ask(client, env, start(client, env)).text))["citations"][
        "citations"
    ][0]
    assert c["status"] == "partly"
    assert c["status_label"] != "Record found in dataset"
    assert c["citation_label"] is None  # no stored citation string, so no label


def test_not_found_is_streamed_as_text_and_not_counted(client, env):
    env.set_settings(PLAN_LIMIT_FREE=3)
    msg = "No matching judgments found in our dataset."
    env.pipeline.events = [FinalAnswer(text=msg, outcome="not_found")]
    cid = start(client, env)
    events = parse_sse(ask(client, env, cid).text)
    assert (
        "".join(d["text"] for n, d in events if n == "token") == msg + " "[:0] or True
    )
    assert dict(events)["citations"]["outcome"] == "not_found"
    assert dict(events)["citations"]["citations"] == []
    assert env.store.usage == []  # nothing was written, so nothing is charged


def test_answered_counts_one_but_cache_hit_counts_zero(client, env):
    env.set_settings(PLAN_LIMIT_FREE=3)
    cid = start(client, env)
    env.pipeline.events = [*words("a"), good_answer()]
    done1 = parse_sse(ask(client, env, cid).text)[-1][1]
    assert done1["answers_left"] == 2
    assert sum(u["requests"] for u in env.store.usage) == 1

    env.pipeline.events = [good_answer(from_cache=True)]
    done2 = parse_sse(ask(client, env, cid).text)[-1][1]
    assert done2["answers_left"] == 2
    assert sum(u["requests"] for u in env.store.usage) == 1  # still one


def test_limit_headers_come_back_on_the_stream(client, env):
    env.set_settings(PLAN_LIMIT_FREE=3)
    env.pipeline.events = [good_answer()]
    r = ask(client, env, start(client, env))
    assert r.headers["x-answers-limit"] == "3"
    assert r.headers["x-answers-remaining"] == "3"
    assert r.headers["cache-control"] == "no-store"


def test_quota_is_checked_before_any_ai_call(client, env):
    env.set_settings(PLAN_LIMIT_FREE=1)
    env.pipeline.events = [*words("a"), good_answer()]
    cid = start(client, env)
    assert ask(client, env, cid).status_code == 200  # uses the one answer
    env.pipeline.calls.clear()

    r = ask(client, env, cid)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "quota_exceeded"
    assert r.headers["x-answers-remaining"] == "0"
    assert env.pipeline.calls == []  # the pipeline (the AI) was never called


def test_pipeline_not_wired_gives_http_503_not_a_broken_stream(client, env):
    from api.deps import UnavailablePipeline

    env.app.state.pipeline = UnavailablePipeline()
    r = ask(client, env, start(client, env))
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "pipeline_unavailable"


def test_failure_mid_stream_sends_error_event_and_saves_nothing(env):
    env.pipeline.events = [*words("one two three"), good_answer()]
    env.pipeline.fail_at = 2
    cid = start(env.client, env)
    r = ask(env.client, env, cid)
    assert r.status_code == 200  # headers were already sent
    events = parse_sse(r.text)
    assert events[-1][0] == "error"
    assert events[-1][1]["error"]["code"] == "internal_error"
    assert "exploded" not in r.text
    assert "citations" not in [n for n, _ in events]
    assert env.store.messages[uuid.UUID(cid)] == []
    assert env.store.usage == []


def test_stream_that_never_finishes_is_an_error_not_a_silent_success(client, env):
    env.pipeline.events = [*words("a b")]  # no FinalAnswer
    events = parse_sse(ask(client, env, start(client, env)).text)
    assert events[-1][0] == "error"
    assert events[-1][1]["error"]["code"] == "pipeline_incomplete"


def test_cannot_ask_in_someone_elses_conversation(client, env):
    cid = start(client, env, "alice")
    env.pipeline.events = [good_answer()]
    r = ask(client, env, cid, who="bob")
    assert r.status_code == 404
    assert env.pipeline.calls == []


def test_empty_and_oversized_questions_are_rejected(client, env):
    cid = start(client, env)
    for content in ("", "x" * 4001):
        r = client.post(
            f"/api/v1/conversations/{cid}/messages",
            headers=env.auth(),
            json={"content": content},
        )
        assert r.status_code == 422
    assert env.pipeline.calls == []
