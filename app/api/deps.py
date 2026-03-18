from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.api_key import APIKeyHeader
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import secrets

from app.core.config import settings
from app.core.security import ALGORITHM
from app.db.session import get_db
from app.models.user import User
from app.schemas.token import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login/access-token")


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)
        if token_data.sub is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    result = await db.execute(select(User).where(User.id == token_data.sub))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user


internal_api_key_header = APIKeyHeader(name="X-Internal-Api-Key", auto_error=True)


async def verify_internal_api_key(api_key: str = Security(internal_api_key_header)):
    if not secrets.compare_digest(api_key, settings.INTERNAL_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid Internal API Key",
        )
    return api_key
