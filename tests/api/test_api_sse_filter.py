"""Unit tests for the safety net that strips citation markers from streamed text."""

import pytest

from api.sse import SourceMarkerFilter, event


def run(chunks):
    f = SourceMarkerFilter()
    out = "".join(f.feed(c) for c in chunks)
    return out + f.flush()


@pytest.mark.parametrize(
    ("chunks", "expected"),
    [
        (["no markers here"], "no markers here"),
        (["see [S1] now"], "see  now"),
        (["see [S1, S3] now"], "see  now"),
        (["see (S2) now"], "see  now"),
        (["split [S", "1] across"], "split  across"),
        (["split [", "S", "1", "] x"], "split  x"),
        (["a (not a marker) b"], "a (not a marker) b"),
        (
            ["unfinished [S"],
            "unfinished [S",
        ),  # nothing came to complete it: let it through
        (["array[0] and f(x)"], "array[0] and f(x)"),
    ],
)
def test_marker_filter(chunks, expected):
    assert run(chunks) == expected


def test_event_format_is_sse():
    assert event("token", {"text": "hi"}) == b'event: token\ndata: {"text": "hi"}\n\n'
