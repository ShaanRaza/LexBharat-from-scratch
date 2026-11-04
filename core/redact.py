"""What may leave the process toward a monitoring vendor (CLAUDE.md section 6, F10).

Two jobs, both pure functions with no vendor import (adapters/telemetry.py is the only
file that wires a vendor, and tests/security/test_telemetry_masking.py fails if that
stops being true):

  * `mask_trace_data` masks the prompts and answers a tracing vendor receives. A run
    that touches CLIENT MATERIAL (an upload, a remembered matter fact) has its text
    WITHHELD whole, because an answer to an upload question quotes the upload; every
    other run has emails, phone numbers and secret-looking tokens replaced. Ids,
    numbers and booleans always pass: they are the part worth keeping (token counts,
    cost, speed).
  * `scrub_error_event` rebuilds an error report from an ALLOW-LIST of fields. Nothing
    else is copied, so a field the SDK adds in a later version is dropped, not leaked.
    Exception MESSAGES are removed (a vendor error can echo its prompt), as are
    request bodies, headers, cookies, query strings, breadcrumbs, log messages,
    stack-frame variables and the user's email.

A run is client material unless `begin_run(client_material=False)` says otherwise. A
code path that forgets to declare itself is therefore withheld, never sent.
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

WITHHELD = "[content withheld: client material]"
EMAIL_MASK, PHONE_MASK, TOKEN_MASK, CLIENT_MASK = (
    "[email]",
    "[phone]",
    "[token]",
    "[client text]",
)

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
_PHONE_RUN = re.compile(r"(?<![\w.])\+?\(?\d[\d\s().\-]{7,}\d(?![\w])")
_TOKEN = re.compile(
    r"(?i)\bbearer\s+[A-Za-z0-9._~+/=\-]{8,}"
    # a JWT (Firebase)
    r"|eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{4,}\.[A-Za-z0-9_\-]{4,}"
    r"|\bAIza[0-9A-Za-z_\-]{30,}|\bAQ\.[0-9A-Za-z_\-]{20,}"  # Gemini key forms
    r"|\bsk-[A-Za-z0-9_\-]{16,}|\bpa-[A-Za-z0-9_\-]{16,}"
    r"|\brzp_(?:live|test)_[A-Za-z0-9]{8,}"
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:\-]{1,64}$")
# the only strings a withheld run still carries: fields of OUR code, never the user's
_KEEP_STRING_KEYS = {"request_id", "model", "step", "feature", "outcome", "error"}
_MAX_DEPTH = 8


@dataclass(frozen=True)
class RunState:
    client_material: bool = True  # fail closed: undeclared means withheld
    strings: frozenset[str] = frozenset()  # exact texts to replace wherever they appear


_RUN: ContextVar[RunState] = ContextVar("redact_run", default=RunState())


def begin_run(*, client_material: bool, strings: tuple[str, ...] = ()) -> None:
    """Declare what the current run (and every task it starts) may send to a vendor."""
    _RUN.set(RunState(client_material, frozenset(s for s in strings if len(s) >= 6)))


def run_state() -> RunState:
    return _RUN.get()


def _phone(m: re.Match[str]) -> str:
    digits = sum(c.isdigit() for c in m.group(0))
    return PHONE_MASK if 10 <= digits <= 14 else m.group(0)


def mask_text(text: str, state: RunState | None = None) -> str:
    """Emails, phone numbers and tokens replaced; text the run registered, too."""
    st = state or run_state()
    for s in sorted(st.strings, key=len, reverse=True):
        text = text.replace(s, CLIENT_MASK)
    text = _TOKEN.sub(TOKEN_MASK, text)
    text = _EMAIL.sub(EMAIL_MASK, text)
    return _PHONE_RUN.sub(_phone, text)


def _safe_key(k: Any) -> str:
    k = str(k)
    return k if _SAFE_ID.match(k) else "[key]"


def _withhold(data: Any, depth: int = 0) -> Any:
    if isinstance(data, bool) or data is None or isinstance(data, int | float):
        return data
    if depth >= _MAX_DEPTH:
        return WITHHELD
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            key = _safe_key(k)
            keep = isinstance(v, str) and k in _KEEP_STRING_KEYS and _SAFE_ID.match(v)
            out[key] = v if keep else _withhold(v, depth + 1)
        return out
    if isinstance(data, list | tuple):
        return [_withhold(v, depth + 1) for v in data]
    return WITHHELD


def _mask(data: Any, st: RunState, depth: int = 0) -> Any:
    if isinstance(data, str):
        return mask_text(data, st)
    if isinstance(data, bool) or data is None or isinstance(data, int | float):
        return data
    if depth >= _MAX_DEPTH:
        return WITHHELD
    if isinstance(data, dict):
        return {mask_text(str(k), st): _mask(v, st, depth + 1) for k, v in data.items()}
    if isinstance(data, list | tuple):
        return [_mask(v, st, depth + 1) for v in data]
    return WITHHELD  # an object we cannot see inside is not sent


def mask_trace_data(*, data: Any, **_: Any) -> Any:
    """The tracing vendor's `mask` callback: every input, output and metadata value."""
    st = run_state()
    return _withhold(data) if st.client_material else _mask(data, st)


# --- error reports ---------------------------------------------------------
_EVENT_KEYS = (
    "event_id",
    "timestamp",
    "platform",
    "level",
    "logger",
    "release",
    "environment",
    "server_name",
    "sdk",
    "fingerprint",
)
_TAG_KEYS = ("request_id", "feature", "outcome", "environment")
_FRAME_KEYS = ("filename", "function", "module", "lineno", "in_app")


def _frames(st: dict | None) -> dict | None:
    if not isinstance(st, dict):
        return None
    out = [
        {k: f[k] for k in _FRAME_KEYS if k in f}  # no vars, no source lines
        for f in st.get("frames", [])
        if isinstance(f, dict)
    ]
    return {"frames": out}


def _exception(block: Any) -> dict | None:
    values = block.get("values") if isinstance(block, dict) else None
    if not isinstance(values, list):
        return None
    out = []
    for v in values:
        if not isinstance(v, dict):
            continue
        item: dict[str, Any] = {
            "type": str(v.get("type", ""))[:80]
        }  # the message is dropped
        if v.get("module"):
            item["module"] = str(v["module"])[:80]
        mech = v.get("mechanism")
        if isinstance(mech, dict):
            item["mechanism"] = {k: mech[k] for k in ("type", "handled") if k in mech}
        fr = _frames(v.get("stacktrace"))
        if fr is not None:
            item["stacktrace"] = fr
        out.append(item)
    return {"values": out}


def _request(req: Any) -> dict | None:
    if not isinstance(req, dict):
        return None
    out = {}
    if req.get("method"):
        out["method"] = str(req["method"])[:10]
    if req.get("url"):
        out["url"] = str(req["url"]).split("?", 1)[0].split("#", 1)[0]  # path only
    return out


def _clean_strings(obj: Any, st: RunState, depth: int = 0) -> Any:
    if isinstance(obj, str):
        return mask_text(obj, st)
    if depth >= _MAX_DEPTH:
        return None
    if isinstance(obj, dict):
        return {k: _clean_strings(v, st, depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_strings(v, st, depth + 1) for v in obj]
    return obj


def scrub_error_event(event: dict, hint: dict | None = None) -> dict | None:
    """The error reporter's `before_send`: a new event from allow-listed fields."""
    out: dict[str, Any] = {k: event[k] for k in _EVENT_KEYS if k in event}
    exc = _exception(event.get("exception"))
    if exc is not None:
        out["exception"] = exc
    req = _request(event.get("request"))
    if req:
        out["request"] = req
    user = event.get("user")
    if isinstance(user, dict) and _SAFE_ID.match(str(user.get("id", ""))):
        out["user"] = {"id": str(user["id"])}  # an id; never the email or the address
    tags = event.get("tags")
    if isinstance(tags, dict):
        keep = {
            k: v for k, v in tags.items() if k in _TAG_KEYS and _SAFE_ID.match(str(v))
        }
        if keep:
            out["tags"] = keep
    if event.get("transaction"):
        out["transaction"] = str(event["transaction"])
    return _clean_strings(out, run_state())
