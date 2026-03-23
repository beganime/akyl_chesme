# app/api/v1/endpoints/users.py
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.api.deps import get_current_user
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Redis — подключаем лениво, с graceful fallback
_redis_client = None

async def get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        # Проверяем соединение
        await client.ping()
        _redis_client = client
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis недоступен, работаем без кэша: {e}")
        return None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    normalized_username = user_in.username.strip().lower()
    result = await db.execute(select(User).where(User.username == normalized_username))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username already exists.")

    db_user = User(username=normalized_username, name=user_in.name)
    db_user.set_password(user_in.password)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


@router.get("/me", response_model=UserResponse)
async def read_user_me(current_user: User = Depends(get_current_user)):
    """Получение профиля (кэшируется в Redis если доступен)."""
    redis = await get_redis()

    if redis:
        try:
            cache_key = f"user_profile:{current_user.id}"
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)

            profile_data = UserResponse.model_validate(current_user).model_dump()
            await redis.setex(cache_key, 300, json.dumps(profile_data, default=str))
        except Exception as e:
            logger.warning(f"Redis ошибка при чтении профиля: {e}")

    return current_user


@router.put("/me", response_model=UserResponse)
async def update_user_me(
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Обновление данных пользователя."""
    if user_in.name is not None:
        current_user.name = user_in.name
    if user_in.avatar_url is not None:
        current_user.avatar_url = user_in.avatar_url

    await db.commit()
    await db.refresh(current_user)

    # Инвалидируем кэш Redis если доступен
    redis = await get_redis()
    if redis:
        try:
            await redis.delete(f"user_profile:{current_user.id}")
        except Exception as e:
            logger.warning(f"Redis ошибка при инвалидации кэша: {e}")

    return current_user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить пользователя по ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user