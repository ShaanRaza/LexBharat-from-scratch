"""Server-sent events (SSE) helpers.

SSE is a plain-text stream: each event is "event: <name>\\ndata: <json>\\n\\n".
The browser reads them one by one as they arrive.
"""

import json
import re
from typing import Any

# Matches things the model writes as source markers: [S1], (S2), [S1, S3] ...
_MARKER = re.compile(r"[\[(]\s*S[1-8](?:\s*[,;]\s*S[1-8])*\s*[\])]")
# The longest a half-written marker can be while we wait for its closing bracket.
_MAX_PENDING = 24


def event(name: str, data: Any) -> bytes:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {name}\ndata: {payload}\n\n".encode()


class SourceMarkerFilter:
    """Safety net: strips citation-shaped markers from streamed text.

    The contract (docs/API.md) is that NOTHING citation-shaped goes out before the single
    verified `citations` event; a user must never see a citation appear and then vanish.
    The pipeline is supposed to hand over clean text, but a marker may arrive split
    across two chunks ("[S" then "1]"), so this holds back a possible half-marker until
    it can tell what it is. Belt and braces: this is the last line of defence.
    """

    def __init__(self) -> None:
        self._pending = ""

    def feed(self, chunk: str) -> str:
        text = _MARKER.sub("", self._pending + chunk)
        # Hold back a trailing "[..." or "(..." that might still become a marker.
        cut = max(text.rfind("["), text.rfind("("))
        if (
            cut != -1
            and len(text) - cut <= _MAX_PENDING
            and not re.search(r"[\])]", text[cut:])
        ):
            self._pending = text[cut:]
            return text[:cut]
        self._pending = ""
        return text

    def flush(self) -> str:
        text = _MARKER.sub("", self._pending)
        self._pending = ""
        return text
