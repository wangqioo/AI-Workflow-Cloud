"""Auth API endpoints: register, login, refresh, me."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.user import User
from . import service
from .dependencies import get_current_user
from .schemas import TokenRefresh, TokenResponse, UserLogin, UserRegister, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    if await service.get_user_by_username(db, body.username):
        raise HTTPException(status_code=409, detail="Username already taken")
    if await service.get_user_by_email(db, body.email):
        raise HTTPException(status_code=409, detail="Email already registered")

    user = await service.create_user(db, body.username, body.email, body.password, body.display_name)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await service.get_user_by_username(db, body.username)
    if user is None or not service.verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    access_token, expires_in = service.create_token(str(user.id), "access")
    refresh_token, _ = service.create_token(str(user.id), "refresh")
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: TokenRefresh, db: AsyncSession = Depends(get_db)):
    payload = service.decode_token(body.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = await service.get_user_by_id(db, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    access_token, expires_in = service.create_token(str(user.id), "access")
    refresh_token, _ = service.create_token(str(user.id), "refresh")
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return user
