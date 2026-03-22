# app/api/v1/endpoints/users.py
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.api.deps import get_current_user

import redis.asyncio as aioredis

router = APIRouter()
logger = logging.getLogger(__name__)

redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

PROFILE_CACHE_TTL = 300  # 5 минут


class UserUpdate(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None


def _profile_key(user_id: str) -> str:
    return f"user_profile:{user_id}"


async def _invalidate_profile_cache(user_id: str):
    """Инвалидируем все кэши связанные с профилем пользователя."""
    try:
        keys = [
            _profile_key(user_id),
            f"user_online:{user_id}",
        ]
        await redis_client.delete(*keys)
    except Exception as e:
        logger.warning(f"Cache invalidation failed for {user_id}: {e}")


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    normalized_username = user_in.username.strip().lower()

    # Проверяем уникальность username
    result = await db.execute(select(User).where(User.username == normalized_username))
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Это имя пользователя уже занято."
        )

    db_user = User(username=normalized_username, name=user_in.name)
    db_user.set_password(user_in.password)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


@router.get("/me", response_model=UserResponse)
async def read_user_me(current_user: User = Depends(get_current_user)):
    """Профиль текущего пользователя — кэшируется в Redis на 5 минут."""
    cache_key = _profile_key(current_user.id)

    try:
        cached = await redis_client.get(cache_key)
        if cached:
            data = json.loads(cached)
            # Конвертируем строки дат обратно
            return data
    except Exception as e:
        logger.warning(f"Redis get failed: {e}")

    try:
        profile_data = UserResponse.model_validate(current_user).model_dump(mode="json")
        await redis_client.setex(cache_key, PROFILE_CACHE_TTL, json.dumps(profile_data))
    except Exception as e:
        logger.warning(f"Redis set failed: {e}")

    return current_user


@router.put("/me", response_model=UserResponse)
async def update_user_me(
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновление профиля — обновляем данные и инвалидируем кэш."""
    changed = False

    if user_in.name is not None and user_in.name.strip():
        current_user.name = user_in.name.strip()
        changed = True

    if user_in.avatar_url is not None:
        current_user.avatar_url = user_in.avatar_url
        changed = True

    if not changed:
        return current_user

    current_user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(current_user)

    # Инвалидируем кэш
    await _invalidate_profile_cache(current_user.id)

    return current_user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить профиль пользователя по ID — кэшируется 2 минуты."""
    cache_key = f"user:{user_id}"

    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    try:
        profile_data = UserResponse.model_validate(user).model_dump(mode="json")
        await redis_client.setex(cache_key, 120, json.dumps(profile_data))
    except Exception:
        pass

    return user