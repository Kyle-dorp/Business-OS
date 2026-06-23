from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import HTTPException, Request, status
from sqlmodel import Session, select

from backend.app.database import engine
from backend.app.models import UserAccount

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-this-secret-at-least-32-bytes")
JWT_ALGORITHM = "HS256"
TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "168"))


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user: UserAccount) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=TOKEN_HOURS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def user_from_token(token: str) -> UserAccount:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session expired. Sign in again.",
        ) from exc

    with Session(engine) as session:
        user = session.get(UserAccount, user_id)
        if not user or not user.active:
            raise HTTPException(status_code=401, detail="Account is inactive or unavailable")
        session.expunge(user)
        return user


def user_from_request(request: Request) -> UserAccount:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in required")
    return user


def manager_from_request(request: Request) -> UserAccount:
    user = user_from_request(request)
    if user.role != "manager":
        raise HTTPException(status_code=403, detail="Manager access required")
    return user


def username_exists(username: str, exclude_user_id: Optional[int] = None) -> bool:
    normalized = username.strip().lower()
    with Session(engine) as session:
        users = session.exec(select(UserAccount)).all()
        return any(
            user.username.strip().lower() == normalized
            and (exclude_user_id is None or user.id != exclude_user_id)
            for user in users
        )
