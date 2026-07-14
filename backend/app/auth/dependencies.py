import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from supabase import Client
from supabase_auth.errors import AuthApiError
from supabase_auth.types import User as SupabaseUser

from app.database import users as users_db
from app.database.models import User as UserModel
from app.database.session import get_db
from app.database.supabase import get_supabase_client

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    client: Client = Depends(get_supabase_client),
) -> SupabaseUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    try:
        response = client.auth.get_user(credentials.credentials)
    except AuthApiError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc

    if response is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    return response.user


def get_current_db_user(
    user: SupabaseUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserModel:
    """Resolves the authenticated Supabase user to our own `users` row,
    creating it on first sight (nothing else creates it)."""
    return users_db.get_or_create_user(db, uuid.UUID(user.id), user.email)
