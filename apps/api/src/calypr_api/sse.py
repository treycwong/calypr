"""Server-sent event plumbing shared by the streaming routes.

A media block runs for thirty seconds to three minutes and says nothing while it waits on the
provider. A stream that goes silent that long gets held back by whatever sits between the API and
the browser (the Vercel proxy, the Railway edge): small writes are buffered until more data
arrives. In production that delayed the Video block's `start` event until the clip was done, so the
block never lit up while it was generating, some runs but not others (CAL-61).

`with_heartbeat` keeps the bytes flowing with an SSE comment (`: ping`) whenever the stream has
been quiet for `interval` seconds. Comment lines carry no `data:` and every client here skips them
(`lib/api.ts` `streamSSE` ignores any frame that doesn't start with `data:`).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

#: An SSE comment: ignored by every parser, enough to flush a buffering proxy.
PING = ": ping\n\n"

#: Headers that ask proxies not to buffer or transform the stream.
SSE_HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}

_DONE = object()


@dataclass(frozen=True)
class _Raised:
    exc: BaseException


async def with_heartbeat(source: AsyncIterator[str], interval: float = 5.0) -> AsyncIterator[str]:
    """Yield everything `source` yields, plus `PING` after every `interval` seconds of quiet.

    `source` runs in its own task and hands items over through a queue, so waiting for the next
    item with a timeout never cancels the run itself. (Timing out an `anext()` directly would
    cancel the generator mid-run.) When the client goes away and this generator is closed or
    cancelled, the task is cancelled, so `source` sees `CancelledError` at its current await,
    which is exactly what the run routes already catch to flush their recorders.
    """
    queue: asyncio.Queue[object] = asyncio.Queue()

    async def pump() -> None:
        try:
            async for item in source:
                queue.put_nowait(item)
        except asyncio.CancelledError:
            raise
        except BaseException as exc:  # noqa: BLE001 — handed to the consumer, re-raised there
            queue.put_nowait(_Raised(exc))
            return
        queue.put_nowait(_DONE)

    task = asyncio.create_task(pump())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=interval)
            except TimeoutError:
                yield PING
                continue
            if item is _DONE:
                return
            if isinstance(item, _Raised):
                raise item.exc
            yield item  # type: ignore[misc]
    finally:
        if not task.done():
            task.cancel()
