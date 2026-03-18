from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional

from app.db.session import get_db
from app.models.user import User
from app.models.bot import BotConfig
from app.api.deps import verify_internal_api_key

router = APIRouter()

class BotCreateRequest(BaseModel):
    username: str
    name: str
    webhook_url: Optional[str] = None

class BotCreateResponse(BaseModel):
    bot_id: str
    username: str
    api_token: str
    webhook_url: Optional[str]

@router.post("/create", response_model=BotCreateResponse, dependencies=[Depends(verify_internal_api_key)])
async def internal_create_bot(payload: BotCreateRequest, db: AsyncSession = Depends(get_db)):
    """
    [INTERNAL BRIDGE] Создает бота в основном ядре "Акыл Чешме".
    Доступно только для Bot Portal через X-Internal-Api-Key.
    """
    # 1. Проверяем, не занят ли username
    stmt = select(User).where(User.username == payload.username)
    existing_user = (await db.execute(stmt)).scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")
        
    # 2. Создаем системного пользователя (бота). Пароль не нужен.
    new_bot_user = User(
        username=payload.username,
        name=payload.name,
        is_bot=True,
        hashed_password=None,
        email=None
    )
    db.add(new_bot_user)
    await db.flush() # Получаем ID без коммита транзакции
    
    # 3. Создаем конфигурацию бота и генерируем API токен
    new_bot_config = BotConfig(
        bot_id=new_bot_user.id,
        webhook_url=payload.webhook_url,
        is_active=True
    )
    db.add(new_bot_config)
    
    await db.commit()
    await db.refresh(new_bot_config)
    
    return {
        "bot_id": new_bot_user.id,
        "username": new_bot_user.username,
        "api_token": new_bot_config.api_token,
        "webhook_url": new_bot_config.webhook_url
    }