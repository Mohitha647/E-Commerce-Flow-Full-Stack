from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_session
from app.models import User
from app.schemas import Token, UserCreate, UserOut
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: UserCreate, session: AsyncSession = Depends(get_session)) -> UserOut:
    existing = (await session.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.post("/login", response_model=Token)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)) -> Token:
    user = (await session.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
