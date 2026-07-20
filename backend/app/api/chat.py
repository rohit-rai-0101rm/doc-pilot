import asyncio
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_db_user
from app.chat.orchestrator import run_grounded_reply
from app.chat.streaming import UI_MESSAGE_STREAM_HEADERS, stream_text_reply
from app.database import chats
from app.database.models import User
from app.database.session import SessionLocal, get_db

router = APIRouter(tags=["chat"])


class CreateThreadRequest(BaseModel):
    title: str | None = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    sequence: int
    created_at: datetime


class ThreadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ThreadWithMessagesResponse(ThreadResponse):
    messages: list[MessageResponse]


@router.get("/threads", response_model=list[ThreadResponse])
def list_threads(
    user: User = Depends(get_current_db_user),
    db: Session = Depends(get_db),
):
    return chats.list_threads(db, user.id)


@router.post("/threads", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
def create_thread(
    body: CreateThreadRequest,
    user: User = Depends(get_current_db_user),
    db: Session = Depends(get_db),
):
    return chats.create_thread(db, user.id, body.title)


@router.get("/threads/{thread_id}", response_model=ThreadWithMessagesResponse)
def get_thread(
    thread_id: uuid.UUID,
    user: User = Depends(get_current_db_user),
    db: Session = Depends(get_db),
):
    thread = chats.get_thread(db, thread_id)

    if thread is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thread not found")

    if thread.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your thread")

    return thread


class ChatStreamMessagePart(BaseModel):
    type: str
    text: str | None = None


class ChatStreamMessage(BaseModel):
    id: str
    role: str
    parts: list[ChatStreamMessagePart]


class ChatStreamRequest(BaseModel):
    threadId: uuid.UUID
    messages: list[ChatStreamMessage]


@router.post("/chat/stream")
async def chat_stream(
    body: ChatStreamRequest,
    user: User = Depends(get_current_db_user),
    db: Session = Depends(get_db),
):
    thread = chats.get_thread(db, body.threadId)

    if thread is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thread not found")

    if thread.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your thread")

    if not body.messages or body.messages[-1].role != "user":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Expected a user message")

    question = "".join(
        part.text or "" for part in body.messages[-1].parts if part.type == "text"
    ).strip()

    if not question:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Empty message")

    chats.add_message(db, body.threadId, role="user", content=question)

    # Run retrieval + the agent + grounding validation to completion before
    # streaming anything, so the client only ever sees an already-validated
    # answer — never partial, unverified model output.
    answer, retrieved_chunks = await run_grounded_reply(db, question)
    reply_text = answer.answer_markdown
    citation_records = [
        {
            "chunk_id": uuid.UUID(citation.chunk_id),
            "page_label": retrieved_chunks[citation.chunk_id].page_label,
            "excerpt": citation.quote,
        }
        for citation in answer.citations
    ]
    thread_id = body.threadId

    async def event_stream():
        async def word_deltas():
            for word in reply_text.split(" "):
                yield word + " "
                await asyncio.sleep(0.03)

        async for chunk in stream_text_reply(word_deltas()):
            yield chunk

        # Uses its own session: by the time this generator actually runs, the
        # request-scoped `db` dependency above has already been torn down —
        # FastAPI closes it as soon as this endpoint returns the
        # StreamingResponse, not after the stream finishes.
        with SessionLocal() as stream_db:
            assistant_message = chats.add_message(
                stream_db, thread_id, role="assistant", content=reply_text
            )
            if citation_records:
                chats.add_citations(stream_db, assistant_message.id, citation_records)

    return StreamingResponse(event_stream(), headers=UI_MESSAGE_STREAM_HEADERS)
