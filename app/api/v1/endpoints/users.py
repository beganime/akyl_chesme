# app/api/v1/endpoints/users.py
import json
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import redis.asyncio as aioredis
from typing import Optional

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.api.deps import get_current_user
from app.core.config import settings

router = APIRouter()

redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

class UserUpdate(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user_in.username))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username already exists.")
    
    db_user = User(username=user_in.username, name=user_in.name)
    db_user.set_password(user_in.password)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@router.get("/me", response_model=UserResponse)
async def read_user_me(current_user: User = Depends(get_current_user)):
    """Получение профиля (кэшируется в Redis на 5 минут)."""
    cache_key = f"user_profile:{current_user.id}"
    
    cached_profile = await redis_client.get(cache_key)
    if cached_profile:
        return json.loads(cached_profile)
    
    profile_data = UserResponse.model_validate(current_user).model_dump()
    await redis_client.setex(cache_key, 300, json.dumps(profile_data))
    
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_user_me(
    user_in: UserUpdate, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Обновление данных и сброс кэша Redis."""
    if user_in.name is not None:
        current_user.name = user_in.name
    if user_in.avatar_url is not None:
        current_user.avatar_url = user_in.avatar_url
        
    await db.commit()
    await db.refresh(current_user)
    
    # ИНВАЛИДАЦИЯ КЭША: Сбрасываем старый профиль, чтобы при следующем GET запросе 
    # пользователь увидел свежие данные.
    cache_key = f"user_profile:{current_user.id}"
    await redis_client.delete(cache_key)
    
    return current_user