# app/api/v1/endpoints/users.py
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import redis.asyncio as aioredis

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.api.deps import get_current_user
from app.core.config import settings

router = APIRouter()

# Инициализация Redis клиента для кэша
redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Регистрация нового пользователя.
    """
    result = await db.execute(select(User).where(User.username == user_in.username))
    if result.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )
    
    db_user = User(
        username=user_in.username,
        name=user_in.name
    )
    db_user.set_password(user_in.password)
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    return db_user

@router.get("/me", response_model=UserResponse)
async def read_user_me(current_user: User = Depends(get_current_user)):
    """
    Получить данные текущего авторизованного пользователя.
    Использует Redis для кэширования профиля (TTL 5 минут), чтобы разгрузить БД.
    """
    cache_key = f"user_profile:{current_user.id}"
    
    # 1. Проверяем кэш
    cached_profile = await redis_client.get(cache_key)
    if cached_profile:
        # Отдаем из оперативной памяти за миллисекунды
        return json.loads(cached_profile)
    
    # 2. Если в кэше нет, берем данные из current_user (которые достались из БД в deps.py)
    # Формируем словарь, используя схему Pydantic для фильтрации данных
    profile_data = UserResponse.model_validate(current_user).model_dump()
    
    # 3. Сохраняем в кэш на 300 секунд (5 минут)
    await redis_client.setex(cache_key, 300, json.dumps(profile_data))
    
    return current_user

