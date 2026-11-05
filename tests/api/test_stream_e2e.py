"""End to end over HTTP: step events -> token events -> ONE citations event -> done."""

from tests.api.conftest import auth, parse_sse


def _ask(client, text, uid="alice"):
    conv = client.post("/api/v1/conversations", json={}, headers=auth(uid)).json()
    r = client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"content": text},
        headers=auth(uid),
    )
    return conv, r


def test_token_events_then_one_citations_then_done(client):
    conv, r = _ask(client, "What is Section 302?")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    all_names = [n for n, _ in events]
    print("EVENT ORDER:", all_names)

    # Progress: step events first, names and counts only, all before the first token.
    first_token = all_names.index("token")
    assert first_token > 0 and set(all_names[:first_token]) == {"step"}
    for _, d in events[:first_token]:
        assert set(d) <= {"step", "found", "kept"}
    assert [d["step"] for _, d in events[:first_token]] == [
        "understanding", "searching", "checking", "writing", "verifying",
    ]  # fmt: skip
    events = events[first_token:]
    names = [n for n, _ in events]

    assert names.count("citations") == 1
    assert names[-1] == "done" and names.count("done") == 1
    assert names[0] == "token"
    ci = names.index("citations")
    assert all(n == "token" for n in names[:ci]) and names[ci + 1 :] == ["done"]

    # Nothing citation-shaped before the citations event carries a status/url:
    for n, d in events[:ci]:
        assert set(d) == {"text"}

    cit = events[ci][1]
    assert cit["credit"].startswith("Data: Open India Law")
    assert (
        cit["data_as_of"] == "6 November 2025"
    )  # judgments only and cit["removed_count"] == 0
    c = cit["citations"][0]
    assert c["status"] in ("verified", "partly") and c["kind"] == "judgment"
    assert c["url"] == "https://example.invalid/fake.pdf" and c["anchor"] == "p3"
    assert "".join(d["text"] for n, d in events if n == "token").startswith("FAKE")

    # Step 11: the answer was saved and the done event names it.
    done = events[-1][1]
    detail = client.get(f"/api/v1/conversations/{conv['id']}", headers=auth()).json()
    assert detail["message_count"] == 2
    assert done["message_id"] == detail["messages"][-1]["id"]


def test_out_of_scope_is_done_with_reason_and_no_citations(client):
    _, r = _ask(client, "outofscope please")
    events = parse_sse(r.text)
    assert [n for n, _ in events] == ["step", "done"]  # stopped after step 3
    events = events[1:]
    assert events[0][1]["refused"] and events[0][1]["reason"] == "out_of_scope"


def test_usage_limit_is_an_error_event(client):
    _, r = _ask(client, "limit")
    events = parse_sse(r.text)
    assert [n for n, _ in events][-1] == "error"
    events = events[-1:]
    assert events[0][1]["code"] == "quota_exceeded" and events[0][1]["request_id"]


def test_pipeline_crash_becomes_error_event_without_leaking_text(client):
    _, r = _ask(client, "boom")
    events = parse_sse(r.text)
    assert [n for n, _ in events][-1] == "error"
    assert "fake failure" not in r.text
