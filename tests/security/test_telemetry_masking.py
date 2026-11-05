# ruff: noqa: E501
"""Langfuse masking and Sentry scrubbing (CLAUDE.md section 6, finding F10): the proof section 6 asks for.

A hostile uploaded document puts ONE known string into the question, a passage, the answer and an
exception message. The tests assert that string reaches neither vendor's payload, with the real SDKs
(sentry-sdk with a capturing transport; langfuse with an in-memory span exporter) when they are
installed, and with a stand-in that applies the same `mask` contract when they are not. A control
shows the capture can see the string when the scrubbing is switched off, so a pass means something.
Pure-function tests of core/redact.py run everywhere. Pipeline steps touched: all (the run is declared
at the top of run_pipeline), 11 for the error path."""

from __future__ import annotations

import json
import logging
import pathlib
import re
from contextlib import contextmanager

import pytest
from security_helpers import (
    QUERY,
    REAL_ID,
    REAL_TEXT,
    ObedientModel,
    RelevantGate,
    make_deps,
    obey,
)

from adapters import telemetry
from core import redact
from core.contracts import PipelineRequest
from core.pipeline import run_pipeline
from core.settings import Settings

STRING = "RAVI-KUMAR-DOB-1970-PAN-ABCDE1234F"  # noqa: S105 - the known string a hostile document plants
EMAIL = "ravi.kumar@example.com"
PHONE = "+91 98765 43210"
ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def fresh_run_state():
    token = redact._RUN.set(redact.RunState())
    yield
    redact._RUN.reset(token)


# --- the pure functions: run everywhere ------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "write to ravi.kumar@example.com today",
        "mail RAVI@Firm.CO.IN now",
        "x+tag@sub.domain.org",
    ],
)
def test_an_email_is_replaced(text):
    out = redact.mask_text(text, redact.RunState(False))
    assert "@" not in out and redact.EMAIL_MASK in out


@pytest.mark.parametrize(
    "phone",
    [
        "+91 98765 43210",
        "098765 43210",
        "98765-43210",
        "9876543210",
        "+1 (415) 555-0132",
        "(022) 2345 6789",
    ],
)
def test_a_phone_number_is_replaced(phone):
    out = redact.mask_text(f"call {phone} please", redact.RunState(False))
    assert redact.PHONE_MASK in out and not re.search(r"\d{4}", out)


@pytest.mark.parametrize(
    "cite",
    [
        "AIR 1973 SC 1461",
        "(2013) 7 S.C.R. 82",
        "Section 138 of the Act",
        "Civil Appeal No. 1234 of 2013",
        "1990-2009",
        "para 15 to 17",
    ],
)
def test_a_citation_or_number_that_is_not_a_phone_is_left_alone(cite):
    assert redact.mask_text(cite, redact.RunState(False)) == cite


@pytest.mark.parametrize(
    "secret",
    [
        "Bearer abcDEF123456789xyz",
        "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0In0.c2lnbmF0dXJlMTIzNA",
        "AIza" + "x" * 35,
        "AQ.Ab8RN6" + "y" * 30,
        "sk-" + "z" * 24,
    ],
)
def test_a_secret_looking_token_is_replaced(secret):
    out = redact.mask_text(f"header was {secret} ok", redact.RunState(False))
    assert redact.TOKEN_MASK in out and secret not in out


def test_text_the_run_registered_is_replaced_wherever_it_appears():
    st = redact.RunState(False, frozenset({STRING}))
    assert STRING not in redact.mask_text(f"a {STRING} b", st)


def test_a_client_material_run_withholds_every_string_and_keeps_numbers_and_ids():
    redact.begin_run(client_material=True)
    out = redact.mask_trace_data(
        data={
            "prompt": f"question {STRING}",
            "nested": [{"text": EMAIL}, ("a", 3)],
            "request_id": "req-123",
            "latency_ms": 41,
            "ok": True,
        }
    )
    assert STRING not in json.dumps(out) and EMAIL not in json.dumps(out)
    assert (
        out["request_id"] == "req-123" and out["latency_ms"] == 41 and out["ok"] is True
    )
    assert out["prompt"] == redact.WITHHELD


def test_a_request_id_that_is_not_a_plain_id_is_withheld_too():
    redact.begin_run(client_material=True)
    out = redact.mask_trace_data(data={"request_id": f"x {STRING}"})
    assert STRING not in json.dumps(out)


def test_a_run_that_never_declared_itself_is_withheld_not_sent():
    # no begin_run: the default state is client material (fail closed)
    assert redact.mask_trace_data(data="anything") == redact.WITHHELD


def test_a_public_run_keeps_the_text_but_masks_emails_and_phones():
    redact.begin_run(client_material=False)
    out = redact.mask_trace_data(data={"prompt": f"{EMAIL} {PHONE} personal liberty"})
    assert out["prompt"] == "[email] [phone] personal liberty"


def test_an_object_the_mask_cannot_see_inside_is_not_sent():
    redact.begin_run(client_material=False)
    assert redact.mask_trace_data(data=object()) == redact.WITHHELD


def _hostile_event():
    return {
        "event_id": "e1", "timestamp": "2026-11-05T00:00:00Z", "platform": "python", "level": "error",
        "logger": "core.pipeline", "release": "r1", "environment": "production", "server_name": "api-1",
        "message": f"pipeline failed for {STRING}",
        "logentry": {"message": f"x {STRING}", "formatted": f"x {STRING}"},
        "exception": {"values": [{
            "type": "RuntimeError", "module": "builtins", "value": f"embedding failed for: {STRING}",
            "mechanism": {"type": "logging", "handled": True, "data": {"q": STRING}},
            "stacktrace": {"frames": [{
                "filename": "core/pipeline.py", "function": "_run", "module": "core.pipeline", "lineno": 80, "in_app": True,
                "abs_path": f"/home/{STRING}/app/core/pipeline.py", "context_line": f"q = '{STRING}'",
                "pre_context": [STRING], "post_context": [STRING], "vars": {"message": STRING, "passages": [STRING]},
            }]},
        }]},
        "request": {
            "method": "POST", "url": f"https://api.example.com/conversations/1?q={STRING}",
            "query_string": f"q={STRING}", "data": {"message": STRING}, "cookies": {"session": STRING},
            "headers": {"Authorization": "Bearer abcDEF123456789xyz", "X-Q": STRING}, "env": {"REMOTE_ADDR": "10.0.0.1"},
        },
        "user": {"id": "u1", "email": EMAIL, "ip_address": "10.0.0.1", "username": STRING},
        "tags": {"request_id": "req-9", "note": STRING},
        "extra": {"document": STRING}, "breadcrumbs": {"values": [{"message": STRING}]},
        "contexts": {"trace": {"trace_id": "t"}, "custom": {"text": STRING}}, "modules": {"a": "1"},
        "threads": {"values": [{"stacktrace": {"frames": [{"vars": {"x": STRING}}]}}]},
        "a_field_a_future_sdk_adds": STRING, "_meta": {"x": STRING},
        "transaction": f"/conversations/{EMAIL}",
    }  # fmt: skip


def test_a_scrubbed_error_event_carries_none_of_the_leaky_fields():
    out = redact.scrub_error_event(_hostile_event())
    blob = json.dumps(out)
    for banned in (
        STRING,
        EMAIL,
        "10.0.0.1",
        "Bearer",
        "abcDEF123456789xyz",
        "session",
    ):
        assert banned not in blob
    assert (
        out["exception"]["values"][0]["type"] == "RuntimeError"
    )  # the type is what is kept
    assert "value" not in out["exception"]["values"][0]
    assert out["request"] == {
        "method": "POST",
        "url": "https://api.example.com/conversations/1",
    }
    assert out["user"] == {"id": "u1"} and out["tags"] == {"request_id": "req-9"}
    assert out["exception"]["values"][0]["stacktrace"]["frames"][0]["lineno"] == 80


@pytest.mark.parametrize(
    "field",
    [
        "message",
        "logentry",
        "extra",
        "breadcrumbs",
        "contexts",
        "modules",
        "threads",
        "a_field_a_future_sdk_adds",
        "_meta",
    ],
)
def test_a_field_outside_the_allow_list_is_not_copied(field):
    assert field not in redact.scrub_error_event(_hostile_event())


# --- the hostile document, end to end --------------------------------------------------------
class _BoomClaimCheck(RelevantGate):
    async def claim_support(self, sentence, passage):
        raise RuntimeError(f"claim check failed while reading: {STRING}")


def _hostile_world(llm_wrapper=lambda llm: llm):
    """An upload chat where the document, the question, the answer and an exception message all carry STRING."""
    s = Settings(FEATURE_UPLOADS=True)
    llm = llm_wrapper(ObedientModel())
    deps = make_deps(settings=s, llm=llm, decisions=_BoomClaimCheck())
    deps.vectors.add_law(REAL_ID, REAL_TEXT, title="Real versus Case")
    deps.vectors.add_upload(
        "up-1", f"{QUERY} {STRING} " + obey((f"Your document says {STRING} [S1]",)),
        user_id="u1", document_id="d1", page_start=1,
    )  # fmt: skip
    req = PipelineRequest(
        "u1", f"{QUERY} {STRING} write to {EMAIL} or call {PHONE}", document_ids=("d1",)
    )
    return deps, req


class _StandInClient:
    """What the tracing SDK does with `mask=`: every input, output and metadata value passes through it."""

    def __init__(self, mask):
        self.mask, self.spans = mask, []

    @contextmanager
    def start_as_current_observation(self, **kw):
        m = self.mask
        self.spans.append(
            {
                "name": kw["name"], "model": kw["model"], "usage": kw.get("usage_details"),
                "input": m(data=kw.get("input")), "output": m(data=kw.get("output")), "metadata": m(data=kw.get("metadata")),
            }
        )  # fmt: skip
        yield self


async def test_langfuse_stand_in_receives_none_of_the_hostile_strings_from_an_upload_run():
    client = _StandInClient(redact.mask_trace_data)
    deps, req = _hostile_world(lambda llm: telemetry.TracedLLM(llm, client))
    result = await run_pipeline(req, deps)
    assert (
        result.outcome == "error" and result.error == "RuntimeError"
    )  # the exception path ran
    blob = json.dumps(client.spans)
    assert client.spans, (
        "the answer model was called, so a generation must have been recorded"
    )
    for banned in (STRING, EMAIL, PHONE, "98765"):
        assert banned not in blob
    assert redact.WITHHELD in blob
    assert all(sp["model"] for sp in client.spans)  # the part worth keeping survives


async def test_a_public_run_is_masked_for_emails_and_phones_but_its_text_is_kept():
    client = _StandInClient(redact.mask_trace_data)
    deps = make_deps(llm=telemetry.TracedLLM(ObedientModel(), client))
    deps.vectors.add_law(REAL_ID, REAL_TEXT, title="Real versus Case")
    await run_pipeline(PipelineRequest("u1", f"{QUERY} {EMAIL} {PHONE}"), deps)
    blob = json.dumps(client.spans)
    assert EMAIL not in blob and PHONE not in blob and "98765" not in blob
    assert redact.EMAIL_MASK in blob and "personal liberty" in blob


async def test_recording_a_trace_never_changes_the_model_result_or_raises():
    class _Down:
        def start_as_current_observation(self, **kw):
            raise RuntimeError(f"vendor down {STRING}")

    deps, req = _hostile_world(lambda llm: telemetry.TracedLLM(llm, _Down()))
    result = await run_pipeline(req, deps)
    assert (
        result.error == "RuntimeError"
    )  # from the claim check, not from the tracing client
    assert STRING not in repr(result)


# --- the same proof against the real SDKs (skipped when a package is not installed) --------------
@pytest.fixture
def sentry_capture():
    sentry_sdk = pytest.importorskip("sentry_sdk")
    from sentry_sdk.transport import Transport

    class Capture(Transport):
        def __init__(self):
            super().__init__()
            self.sent: list[bytes] = []

        def capture_envelope(self, envelope):
            self.sent.append(envelope.serialize())

    cap = Capture()
    yield sentry_sdk, cap
    sentry_sdk.flush()
    sentry_sdk.get_client().close()


def _init_sentry(sentry_sdk, cap, *, scrub: bool):
    sentry_sdk.init(
        dsn="https://public@o0.ingest.sentry.io/0", transport=cap, send_default_pii=True,
        include_local_variables=True, include_source_context=True, traces_sample_rate=0.0,
    )  # fmt: skip


async def test_control_the_real_error_reporter_sees_the_string_when_nothing_scrubs_it(
    sentry_capture,
):
    sentry_sdk, cap = sentry_capture
    _init_sentry(sentry_sdk, cap, scrub=False)
    deps, req = _hostile_world()
    await run_pipeline(req, deps)
    sentry_sdk.flush()
    assert cap.sent, "the logged exception must have produced an event"
    assert STRING.encode() in b"".join(cap.sent), (
        "the control must be able to see the string, or the pass below proves nothing"
    )


async def test_the_real_error_reporter_receives_none_of_the_hostile_strings(
    sentry_capture,
):
    sentry_sdk, cap = sentry_capture
    settings = Settings(SENTRY_DSN="https://public@o0.ingest.sentry.io/0")
    assert telemetry.init_error_reporting(settings, transport=cap) is True
    deps, req = _hostile_world()
    result = await run_pipeline(req, deps)
    assert result.error == "RuntimeError"
    sentry_sdk.flush()
    sent = b"".join(cap.sent)
    assert sent, "an event must have been sent, or this test checks nothing"
    assert b"RuntimeError" in sent  # what is kept
    for banned in (STRING, EMAIL, PHONE, "98765", QUERY):
        assert banned.encode() not in sent


async def test_the_real_tracing_client_exports_none_of_the_hostile_strings():
    pytest.importorskip("langfuse")
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    settings = Settings(
        LANGFUSE_PUBLIC_KEY="pk-lf-test",
        LANGFUSE_SECRET_KEY="sk-lf-test",  # noqa: S106
        LANGFUSE_HOST="http://127.0.0.1:9",
    )
    client = telemetry.make_trace_client(settings, span_exporter=exporter, flush_at=1)
    assert client is not None
    deps, req = _hostile_world(lambda llm: telemetry.TracedLLM(llm, client))
    await run_pipeline(req, deps)
    client.flush()
    spans = exporter.get_finished_spans()
    assert spans, "a generation must have been exported, or this test checks nothing"
    blob = json.dumps([dict(sp.attributes or {}) for sp in spans], default=str)
    for banned in (STRING, EMAIL, PHONE, "98765"):
        assert banned not in blob
    assert redact.WITHHELD in blob


# --- the tripwire: the vendors live in ONE file, and that file masks and scrubs ------------------
def test_no_vendor_is_mentioned_outside_the_one_file_that_masks_and_scrubs():
    from test_injection_uploads import vendor_mentions

    assert vendor_mentions(ROOT) == []


def test_that_one_file_builds_nothing_without_its_mask_and_scrub_hooks():
    src = (ROOT / "adapters" / "telemetry.py").read_text()
    # every client construction carries the hook
    assert re.search(r"Langfuse\([^)]*mask=redact\.mask_trace_data", src, re.S)
    init = src[src.index("sentry_sdk.init(") :]
    init = init[: init.index("\n    )")]
    for must in (
        "before_send=redact.scrub_error_event",
        "send_default_pii=False",
        "include_local_variables=False",
        'max_request_body_size="never"',
        "before_breadcrumb",
        "before_send_transaction",
    ):
        assert must in init, must
    # no callback route into a vendor that this file does not control
    assert not re.search(
        r"success_callback|failure_callback|litellm\.callbacks|set_verbose", src
    )


def test_no_logging_in_the_telemetry_path_interpolates_anything():
    # the tripwire in test_injection_uploads covers adapters/ and core/; this pins the two new files by name
    from test_injection_uploads import log_calls_with_data

    assert [
        b for b in log_calls_with_data(ROOT) if "telemetry" in b or "redact" in b
    ] == []
    assert logging.getLogger("adapters.telemetry")
