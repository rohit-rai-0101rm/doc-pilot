from fastapi import APIRouter, Depends
from supabase_auth.types import User

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)) -> dict[str, str | None]:
    return {"id": user.id, "email": user.email}
