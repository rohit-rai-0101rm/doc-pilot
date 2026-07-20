import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import ChatMessage, ChatThread


def list_threads(db: Session, user_id: uuid.UUID) -> list[ChatThread]:
    stmt = (
        select(ChatThread)
        .where(ChatThread.user_id == user_id)
        .order_by(ChatThread.updated_at.desc())
    )
    return list(db.scalars(stmt))


def create_thread(db: Session, user_id: uuid.UUID, title: str | None) -> ChatThread:
    thread = ChatThread(user_id=user_id, title=title)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def get_thread(db: Session, thread_id: uuid.UUID) -> ChatThread | None:
    return db.get(ChatThread, thread_id)


def add_message(db: Session, thread_id: uuid.UUID, role: str, content: str) -> ChatMessage:
    last_sequence = db.scalar(
        select(func.max(ChatMessage.sequence)).where(ChatMessage.thread_id == thread_id)
    )
    message = ChatMessage(
        thread_id=thread_id,
        role=role,
        content=content,
        sequence=(last_sequence or 0) + 1,
    )
    db.add(message)

    thread = db.get(ChatThread, thread_id)
    thread.updated_at = datetime.now(UTC)

    db.commit()
    db.refresh(message)
    return message
