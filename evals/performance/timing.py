"""Timing capture for the performance targets in CLAUDE.md section 10 (pipeline steps 1-11; measurement only).

Plain words: Langfuse is not wired (finding F10) and must not be before the masking work, so the runner times itself.
This module holds the parts that need no vendor: a recorder for per-step and per-vendor-call intervals, the
arithmetic (percentiles, how much of a step was a vendor call), and a sampler that watches the shared Qdrant instance
so a number taken while another job was hammering it is flagged and re-run, never reported.

Nothing here changes behaviour: wrappers call the real function and note when it started and ended.
"""

from __future__ import annotations

import functools
import os
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

QDRANT_PORT = 7333
# A sample is contended when another client holds a connection to the instance (the dump job that spoiled a run on
# 4 Nov 2026 was one: PID 5313, server at 831%). Server CPU alone is NOT the test: our own hybrid query alone drives
# the server to 400% on this 10-core machine (seen in the smoke run), so a CPU threshold flags our own load. CPU is
# recorded and used only for the idle check before the run starts.
QUIET_CPU_PERCENT = 50.0


@dataclass
class Interval:
    name: str
    t0: float
    t1: float

    @property
    def seconds(self) -> float:
        return self.t1 - self.t0


@dataclass
class Recorder:
    """One question's intervals: pipeline steps and vendor calls, on one monotonic clock."""

    steps: list[Interval] = field(default_factory=list)
    vendor: list[Interval] = field(
        default_factory=list
    )  # name = "gemini:rate_passage", "voyage:rerank", ...
    notes: dict = field(default_factory=dict)

    def reset(self) -> None:
        self.steps.clear()
        self.vendor.clear()
        self.notes.clear()


REC = Recorder()


def timed_step(name: str, fn: Callable, rec: Recorder = REC) -> Callable:
    """Wrap a pipeline step (sync or async), noting when it started and ended."""
    if _is_async(fn):

        @functools.wraps(fn)
        async def awrapper(*a, **k):
            t0 = time.perf_counter()
            try:
                return await fn(*a, **k)
            finally:
                rec.steps.append(Interval(name, t0, time.perf_counter()))

        return awrapper

    @functools.wraps(fn)
    def wrapper(*a, **k):
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            rec.steps.append(Interval(name, t0, time.perf_counter()))

    return wrapper


def _is_async(fn: Callable) -> bool:
    import inspect

    return inspect.iscoroutinefunction(fn)


async def timed_call(kind: str, awaitable, rec: Recorder = REC):
    """Await one vendor call and record it as a vendor interval."""
    t0 = time.perf_counter()
    try:
        return await awaitable
    finally:
        rec.vendor.append(Interval(kind, t0, time.perf_counter()))


# ----------------------------------------------------------------------------------------------------------------------
# arithmetic
# ----------------------------------------------------------------------------------------------------------------------
def percentile(values: list[float], q: float) -> float | None:
    """Linear-interpolated percentile (q in 0-100); None for no values. Never an average."""
    return float(np.percentile(np.asarray(values, dtype=float), q)) if values else None


def p50_p95(values: list[float]) -> tuple[float | None, float | None]:
    return percentile(values, 50), percentile(values, 95)


def union_seconds(intervals: list[tuple[float, float]]) -> float:
    """Total length covered by possibly overlapping intervals (calls that ran in parallel count once)."""
    total, end = 0.0, None
    for a, b in sorted(intervals):
        if end is None or a > end:
            total += b - a
            end = b
        elif b > end:
            total += b - end
            end = b
    return total


def vendor_share(step: Interval, vendor: list[Interval], prefix: str = "") -> float:
    """Seconds of `step` spent inside vendor calls (clipped to the step; parallel calls count once)."""
    clipped = [
        (max(v.t0, step.t0), min(v.t1, step.t1))
        for v in vendor
        if v.name.startswith(prefix) and v.t1 > step.t0 and v.t0 < step.t1
    ]
    return union_seconds(clipped)


# ----------------------------------------------------------------------------------------------------------------------
# is the shared instance quiet?
# ----------------------------------------------------------------------------------------------------------------------
@dataclass
class LoadSample:
    t: float  # perf_counter
    qdrant_cpu: float | None
    load1: float
    foreign_clients: tuple[int, ...]


def _qdrant_pid() -> int | None:
    out = subprocess.run(  # noqa: S603
        ["lsof", "-nP", f"-iTCP:{QDRANT_PORT}", "-sTCP:LISTEN", "-Fp"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    pids = [int(x[1:]) for x in out.split() if x.startswith("p")]
    return pids[0] if pids else None


def sample_load(qdrant_pid: int | None, own_pid: int | None = None) -> LoadSample:
    """One look at the shared instance: its CPU, the machine load, and any client that is not this process."""
    own_pid = own_pid or os.getpid()
    cpu = None
    if qdrant_pid:
        out = subprocess.run(  # noqa: S603
            ["ps", "-o", "%cpu=", "-p", str(qdrant_pid)],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        cpu = float(out) if out else None
    conns = subprocess.run(  # noqa: S603
        ["lsof", "-nP", f"-iTCP:{QDRANT_PORT}", "-sTCP:ESTABLISHED", "-Fp"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    pids = {int(x[1:]) for x in conns.split() if x.startswith("p")}
    foreign = tuple(sorted(pids - {own_pid, qdrant_pid or -1}))
    return LoadSample(time.perf_counter(), cpu, os.getloadavg()[0], foreign)


def is_contended(s: LoadSample) -> bool:
    return bool(s.foreign_clients)


def is_quiet(samples: list[LoadSample]) -> bool:
    """Before starting: no other client on the port and the server idle."""
    return bool(samples) and all(
        not s.foreign_clients
        and (s.qdrant_cpu is None or s.qdrant_cpu < QUIET_CPU_PERCENT)
        for s in samples
    )


def contended_between(
    samples: list[LoadSample], t0: float, t1: float
) -> list[LoadSample]:
    """Samples taken inside [t0, t1] (the question's window, one sample either side) that show contention."""
    return [s for s in samples if t0 - 3.0 <= s.t <= t1 + 3.0 and is_contended(s)]


class LoadSampler(threading.Thread):
    """Samples the instance every `every` seconds until stopped."""

    def __init__(self, every: float = 2.0):
        super().__init__(daemon=True)
        self.every, self.samples, self._stop_evt = every, [], threading.Event()
        self.qdrant_pid = _qdrant_pid()

    def run(self) -> None:
        while not self._stop_evt.is_set():
            self.samples.append(sample_load(self.qdrant_pid))
            self._stop_evt.wait(self.every)

    def stop(self) -> None:
        self._stop_evt.set()
