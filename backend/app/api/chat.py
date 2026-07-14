import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_db_user
from app.database import chats
from app.database.models import User
from app.database.session import get_db

router = APIRouter(prefix="/threads", tags=["chat"])


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


@router.get("", response_model=list[ThreadResponse])
def list_threads(
    user: User = Depends(get_current_db_user),
    db: Session = Depends(get_db),
):
    return chats.list_threads(db, user.id)


@router.post("", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
def create_thread(
    body: CreateThreadRequest,
    user: User = Depends(get_current_db_user),
    db: Session = Depends(get_db),
):
    return chats.create_thread(db, user.id, body.title)


@router.get("/{thread_id}", response_model=ThreadWithMessagesResponse)
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
