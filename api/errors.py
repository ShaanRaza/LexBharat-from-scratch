"""One error format and a request ID on every response (docs/API.md)."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from api.schemas import ErrorCode


class ApiError(Exception):
    def __init__(self, status: int, code: ErrorCode, message: str):
        self.status, self.code, self.message = status, code, message


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", "") or "unknown"


def error_response(request: Request, status: int, code: str, message: str):
    rid = request_id_of(request)
    return JSONResponse(
        {"error": {"code": code, "message": message, "request_id": rid}},
        status_code=status,
        headers={"X-Request-ID": rid},
    )


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.request_id = (
            request.headers.get("x-request-id") or uuid.uuid4().hex
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response


_CODES = {
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    429: "rate_limited",
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(request: Request, exc: ApiError):
        return error_response(request, exc.status, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = _CODES.get(exc.status_code, "internal_error")
        return error_response(request, exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _val(request: Request, exc: RequestValidationError):
        return error_response(request, 422, "validation_error", "Invalid request.")

    @app.exception_handler(Exception)
    async def _any(request: Request, exc: Exception):
        # Never echo exception text: it may hold a secret or document text.
        return error_response(request, 500, "internal_error", "Something went wrong.")
