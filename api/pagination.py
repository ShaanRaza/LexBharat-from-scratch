"""Cursor pagination (docs/API.md: on every list).

A cursor is an opaque string the client passes back unchanged. Inside it is the
(created_at, id) of the last row seen, so the next page starts right after it.
"""

import base64
import binascii
from datetime import datetime
from uuid import UUID

from api.errors import ApiError

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def encode_cursor(created_at: datetime, row_id: UUID) -> str:
    raw = f"{created_at.isoformat()}|{row_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> tuple[datetime, UUID] | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        ts, _, ident = base64.urlsafe_b64decode(padded).decode().partition("|")
        return datetime.fromisoformat(ts), UUID(ident)
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise ApiError(400, "invalid_cursor", "That page link is not valid.") from None
