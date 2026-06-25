"""Global concurrency limit for local model inference.

The stress test surfaced this: a burst of concurrent ``/ask`` requests drove a
4 GB GPU into a CUDA out-of-memory (``cudaMalloc failed``), which crashed the
Ollama runner and left VRAM pinned — the box couldn't recover without manual
intervention. Concurrent local inference is the trigger.

This caps how many model calls run at once, app-wide, so a burst *queues* behind
the gate instead of over-committing the GPU. It is deliberately small by default
(2) and tunable via ``AMAGRA_MAX_CONCURRENT_INFERENCE``. Cloud providers don't
touch local VRAM, so only the local coordinator path is gated.

Usage:
    from infrastructure.inference_limit import inference_slot
    async with inference_slot():
        result = await loop.run_in_executor(None, lambda: coordinator.invoke(...))
"""
from __future__ import annotations

import asyncio
import contextlib
import os

_LIMIT = max(1, int(os.environ.get("AMAGRA_MAX_CONCURRENT_INFERENCE", "2")))

# Cached per running loop so tests (which spin up fresh loops) don't reuse a
# semaphore bound to a dead loop.
_sem: asyncio.Semaphore | None = None
_sem_loop: asyncio.AbstractEventLoop | None = None


def limit() -> int:
    """The configured maximum number of concurrent in-flight inference calls."""
    return _LIMIT


def _get() -> asyncio.Semaphore:
    global _sem, _sem_loop
    loop = asyncio.get_running_loop()
    if _sem is None or _sem_loop is not loop:
        _sem = asyncio.Semaphore(_LIMIT)
        _sem_loop = loop
    return _sem


@contextlib.asynccontextmanager
async def inference_slot():
    """Hold one of ``limit()`` inference slots for the duration of the block."""
    async with _get():
        yield
