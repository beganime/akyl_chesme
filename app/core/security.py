from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_password.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_byte_enc = plain_password.encode("utf-8")
    hashed_password_byte_enc = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_byte_enc, hashed_password_byte_enc)


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode = {"exp": expire, "iat": now, "nbf": now, "sub": str(subject), "type": "access"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
