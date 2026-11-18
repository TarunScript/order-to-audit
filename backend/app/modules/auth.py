"""Auth endpoints for login and current user profile."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
    Token,
)
from app.core.database import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    full_name: str
    active: bool

    class Config:
        from_attributes = True


@router.post("/login", response_model=Token)
async def login(
    login_data: Optional[LoginRequest] = None,
    form_data: Optional[OAuth2PasswordRequestForm] = Depends(lambda: None),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user with username and password, return JWT token."""
    username = None
    password = None

    if login_data:
        username = login_data.username
        password = login_data.password
    elif form_data:
        username = form_data.username
        password = form_data.password

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_INPUT", "message": "Username and password required", "details": None},
        )

    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Incorrect username or password", "details": None},
        )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "INACTIVE_USER", "message": "User account is disabled", "details": None},
        )

    token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.id}
    )
    return Token(
        access_token=token,
        token_type="bearer",
        role=user.role,
        username=user.username,
        user_id=user.id,
    )


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the profile of currently authenticated user."""
    return current_user
