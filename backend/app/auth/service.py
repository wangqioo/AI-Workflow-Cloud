"""Auth business logic: password hashing, JWT tokens, user CRUD."""

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(user_id: str, token_type: str = "access") -> tuple[str, int]:
    """Create a JWT token. Returns (token, expires_in_seconds)."""
    now = datetime.now(timezone.utc)
    if token_type == "access":
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    else:
        expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)

    expire = now + expires_delta
    payload = {
        "sub": user_id,
        "type": token_type,
        "iat": now,
        "exp": expire,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token. Returns payload or None."""
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession, username: str, email: str, password: str, display_name: str | None = None
) -> User:
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user
