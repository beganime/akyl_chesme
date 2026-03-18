# app/api/deps.py
import json
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.api_key import APIKeyHeader
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import redis.asyncio as aioredis

from app.core.config import settings
from app.core.security import ALGORITHM
from app.core.db import AsyncSessionLocal
from app.models.user import User
from app.schemas.token import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login/access-token")
# Инициализируем клиент Redis
redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

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
    except JWTError:
        raise credentials_exception
    
    # Прод-оптимизация: Сначала проверяем Redis
    cache_key = f"auth_user:{token_data.sub}"
    cached_user = await redis_client.get(cache_key)
    
    if cached_user:
        # Возвращаем объект User из кэша (в виде словаря/модели)
        user_dict = json.loads(cached_user)
        return User(**user_dict)

    # Если в кэше нет — идем в БД
    result = await db.execute(select(User).where(User.id == token_data.sub))
    user = result.scalars().first()
    
    if user is None:
        raise credentials_exception
        
    # Сохраняем в кэш на 10 минут, чтобы разгрузить БД
    user_data = {
        "id": user.id,
        "username": user.username,
        "is_bot": user.is_bot,
        "name": user.name,
        "avatar_url": user.avatar_url
    }
    await redis_client.setex(cache_key, 600, json.dumps(user_data))
    
    return user

# =================================================================
# НОВОЕ: ЗАЩИТА ДЛЯ МЕЖСЕРВЕРНОГО МОСТА (S2S)
# =================================================================
internal_api_key_header = APIKeyHeader(name="X-Internal-Api-Key", auto_error=True)

async def verify_internal_api_key(api_key: str = Security(internal_api_key_header)):
    """
    Проверяет, что запрос пришел от твоего доверенного Портала Ботов.
    """
    # Используем SECRET_KEY проекта как пароль между нашими серверами
    if api_key != settings.SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid Internal API Key"
        )
    return api_key