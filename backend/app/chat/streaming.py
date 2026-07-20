"""Frames a text reply as an AI SDK UI Message Stream (protocol v1).

Wire format verified against the installed `ai` package (v7.0.26): each
event is `data: <json>\\n\\n` (SSE), terminated by `data: [DONE]\\n\\n`.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

UI_MESSAGE_STREAM_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "x-vercel-ai-ui-message-stream": "v1",
    "x-accel-buffering": "no",
}


def _sse(chunk: dict) -> str:
    return f"data: {json.dumps(chunk)}\n\n"


async def stream_text_reply(text_deltas: AsyncIterator[str]) -> AsyncIterator[str]:
    text_id = str(uuid.uuid4())

    yield _sse({"type": "start"})
    yield _sse({"type": "start-step"})
    yield _sse({"type": "text-start", "id": text_id})

    async for delta in text_deltas:
        yield _sse({"type": "text-delta", "id": text_id, "delta": delta})

    yield _sse({"type": "text-end", "id": text_id})
    yield _sse({"type": "finish-step"})
    yield _sse({"type": "finish"})
    yield "data: [DONE]\n\n"
