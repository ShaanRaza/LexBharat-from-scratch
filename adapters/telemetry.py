"""The ONLY file that wires Langfuse (AI-call traces) and Sentry (errors). F10.

Plain words: both vendors are off unless their keys are set, and when on they receive
nothing that `core/redact.py` has not masked or scrubbed. The SDKs are imported inside
the functions, so the product runs without them installed. A static test
(tests/security/test_telemetry_masking.py) fails if either vendor is mentioned outside
this file, or if a client is built here without its mask / scrub hook.

NOT WIRED INTO THE APP YET: nothing calls `init_error_reporting` or wraps the writing
model in `TracedLLM`. Those are two lines in the platform lane (the app factory and the
dependency builder). Until they exist nothing is sent, and the CLAUDE.md section 6 line
stays true for the reason it was true before this file did.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from adapters.llm import LLM, LLMResult
from core import redact
from core.settings import Settings

log = logging.getLogger(__name__)


def init_error_reporting(settings: Settings, *, transport: Any = None) -> bool:
    """Start the error reporter, scrubbed. False, and nothing started, with no DSN."""
    dsn = settings.SENTRY_DSN.get_secret_value()
    if not dsn:
        return False
    try:
        import sentry_sdk
    except (
        ImportError
    ) as e:  # a DSN is set but the package is not: refuse, do not send raw
        raise RuntimeError("SENTRY_DSN is set but sentry-sdk is not installed") from e
    sentry_sdk.init(
        dsn=dsn,
        environment=settings.ENVIRONMENT,
        send_default_pii=False,
        include_local_variables=False,  # frame variables hold the question, passages
        include_source_context=False,
        max_request_body_size="never",
        max_breadcrumbs=0,
        traces_sample_rate=0.0,
        before_send=redact.scrub_error_event,
        before_send_transaction=lambda event, hint: None,
        before_breadcrumb=lambda crumb, hint: None,
        transport=transport,
    )
    return True


def make_trace_client(settings: Settings, **overrides: Any) -> Any | None:
    """The tracing client, masked. None when the keys are not set."""
    public, secret = (
        settings.LANGFUSE_PUBLIC_KEY,
        settings.LANGFUSE_SECRET_KEY.get_secret_value(),
    )
    if not (public and secret):
        return None
    try:
        from langfuse import Langfuse
    except ImportError as e:
        raise RuntimeError("Langfuse keys are set but langfuse is not installed") from e
    return Langfuse(
        public_key=public,
        secret_key=secret,
        host=settings.LANGFUSE_HOST or None,
        mask=redact.mask_trace_data,
        **overrides,
    )


class TracedLLM:
    """Wraps any `LLM`; records each call as a generation on the (masked) client.
    Recording never changes the result and never raises into the pipeline."""

    def __init__(self, inner: LLM, client: Any):
        self._inner, self._client = inner, client

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        model: str,
        max_tokens: int = 1024,
        json_schema: dict | None = None,
    ) -> LLMResult:
        start = time.perf_counter()
        try:
            r = await self._inner.complete(
                prompt,
                system=system,
                model=model,
                max_tokens=max_tokens,
                json_schema=json_schema,
            )
        except Exception as e:
            self._record(prompt, system, model, None, None, start, type(e).__name__)
            raise
        self._record(prompt, system, model, r.text, r, start, None)
        return r

    def _record(
        self,
        prompt: str,
        system: str,
        model: str,
        text: str | None,
        r: LLMResult | None,
        start: float,
        error: str | None,
    ) -> None:
        meta: dict[str, Any] = {"latency_ms": int((time.perf_counter() - start) * 1000)}
        if error:
            meta["error"] = error  # the type name only, never the message
        try:
            with self._client.start_as_current_observation(
                as_type="generation",
                name="llm",
                model=model,
                input={"system": system, "prompt": prompt},
                output=text,
                metadata=meta,
                usage_details=(
                    {"input": r.input_tokens, "output": r.output_tokens} if r else None
                ),
            ):
                pass
        except Exception:  # noqa: BLE001
            log.warning("trace recording failed")
