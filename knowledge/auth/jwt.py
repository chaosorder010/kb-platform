from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt

DEFAULT_JWT_SECRET = "kb-platform-dev-secret-change-me"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def get_jwt_secret() -> str:
    return os.getenv("JWT_SECRET", DEFAULT_JWT_SECRET)


def create_access_token(subject: str, extra: dict | None = None) -> str:
    payload = {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, get_jwt_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, get_jwt_secret(), algorithms=[ALGORITHM])
