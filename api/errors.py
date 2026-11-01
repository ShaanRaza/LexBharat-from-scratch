"""One error format and one request ID for every response (docs/API.md).

Every error the API sends looks exactly like this, nothing else:
    {"error": {"code": "quota_exceeded", "message": "...", "request_id": "..."}}
`code` is for machines (the website picks a screen from it); `message` is for people.
"""

import logging
import re
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# The request ID of the request being handled right now. A ContextVar is a
# "variable that is separate for each request", so concurrent requests never mix.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

log = logging.getLogger("api")

# Only accept a caller-supplied ID if it is short and boring (stops log injection).
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class ApiError(Exception):
    """Raise this from a route or dependency to send the standard error body."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers or {}


def error_body(code: str, message: str) -> dict:
    return {
        "error": {"code": code, "message": message, "request_id": request_id_var.get()}
    }


# Fallback codes for errors raised by FastAPI/Starlette themselves (unknown route, ...).
_HTTP_CODES = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    429: "rate_limited",
}


class RequestIdMiddleware:
    """Gives every request an ID and puts it on the response as `X-Request-ID`.

    It is a plain ASGI middleware (not BaseHTTPMiddleware) so it never buffers or
    breaks the streaming (SSE) responses.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        supplied = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = supplied if _SAFE_ID.match(supplied) else uuid.uuid4().hex
        token = request_id_var.set(request_id)

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)


class RequestIdLogFilter(logging.Filter):
    """Writes the request ID into every log line, so one ID finds everything."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return JSONResponse(
            error_body(exc.code, exc.message),
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        return JSONResponse(
            error_body(code, str(exc.detail)),
            status_code=exc.status_code,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        # Only field names and rule text, never the submitted values: a value could
        # be a user's question or a client's name.
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'][1:]) or 'body'}: {e['msg']}"
            for e in exc.errors()
        )
        return JSONResponse(
            error_body("invalid_request", problems or "Invalid request."),
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        # Log the traceback (with the request ID) but tell the caller nothing internal.
        log.exception("unhandled error")
        return JSONResponse(
            error_body("internal_error", "Something went wrong on our side."),
            status_code=500,
        )
