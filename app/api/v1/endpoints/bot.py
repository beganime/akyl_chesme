# app/api/v1/endpoints/bot.py
import secrets
from fastapi import APIRouter, Header, HTTPException, Depends, status, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime
from typing import Optional, Dict, Any

from app.core.config import settings
from app.db.session import get_db
from app.models.bot import BotConfig
from app.models.user import User
# ... остальные импорты (Chat, Message, ws_manager и т.д.) ...

router = APIRouter()

# --- 1. ЗАЩИТА МОСТА ПОД ДОКУМЕНТАЦИЮ DJANGO ---
# Джанго отправляет X-API-Key (согласно пункту 5.1)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

async def verify_django_portal_key(api_key: str = Security(api_key_header)):
    # В настройках .env ядра должен быть CORE_API_KEY, совпадающий с Джанго
    # Для простоты пока сверяем с SECRET_KEY, или заведи settings.CORE_API_KEY
    if api_key != settings.SECRET_KEY: 
        raise HTTPException(status_code=403, detail="Invalid CORE_API_KEY")
    return api_key


# --- 2. СХЕМА ЗАПРОСА СТРОГО ПО ПУНКТУ 5.1 ---
class BotRegisterDjangoRequest(BaseModel):
    bot_username: str
    name: str
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    webhook_url: str
    commands: Optional[Dict[str, str]] = None
    developer_id: str
    developer_email: Optional[str] = None


# --- 3. ЭНДПОИНТ РЕГИСТРАЦИИ (POST /api/v1/bot/bots) ---
# Обрати внимание: в router.py префикс /bot, значит тут делаем /bots -> будет /bot/bots 
# (или перенастрой в router.py, чтобы было ровно /api/v1/bots)
@router.post("/bots", dependencies=[Depends(verify_django_portal_key)])
async def register_bot_from_django(payload: BotRegisterDjangoRequest, db: AsyncSession = Depends(get_db)):
    
    # 1. Проверяем уникальность bot_username
    stmt = select(User).where(User.username == payload.bot_username)
    if (await db.execute(stmt)).scalars().first():
        # Отвечаем статусом 409, как просит таблица 5.3 в доке
        raise HTTPException(status_code=409, detail="Имя бота уже используется")
        
    # 2. Создаем юзера-бота
    new_bot_user = User(
        username=payload.bot_username,
        name=payload.name,
        avatar_url=payload.avatar_url,
        is_bot=True
    )
    db.add(new_bot_user)
    await db.flush() 
    
    # 3. Генерируем токен сами (как ожидает Джанго)
    generated_token = f"{secrets.randbelow(99999)}:{secrets.token_urlsafe(16)}"
    
    # 4. Настраиваем бота
    new_bot_config = BotConfig(
        bot_id=new_bot_user.id,
        api_token=generated_token,
        webhook_url=payload.webhook_url,
        is_active=True
    )
    db.add(new_bot_config)
    await db.commit()
    
    # 5. Возвращаем ответ СТРОГО ПО ПУНКТУ 5.2
    return {
        "success": True,
        "message": "Бот успешно зарегистрирован",
        "data": {
            "bot": {
                "id": new_bot_user.id,
                "bot_username": new_bot_user.username,
                "status": "active"
            },
            "token": generated_token,
            "jwt_token": "not_required_for_bot_api", # Заглушка, если боты юзают только x-bot-token
            "deep_link": f"https://akyl-cheshmesi.ru/b/{new_bot_user.username}"
        }
    }
# =================================================================
# ЭНДПОИНТ 2: ОТПРАВКА СООБЩЕНИЙ (ВЫЗЫВАЕТ САМ БОТ)
# =================================================================
class BotMessageRequest(BaseModel):
    chat_id: str
    text: str

@router.post("/sendMessage", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def bot_send_message(
    payload: BotMessageRequest,
    x_bot_token: str = Header(..., description="API токен бота (например 12345:ABC...)"),
    db: AsyncSession = Depends(get_db)
):
    # ... (здесь остается твой старый код функции bot_send_message без изменений) ...
    stmt = select(BotConfig).where(BotConfig.api_token == x_bot_token, BotConfig.is_active == True)
    result = await db.execute(stmt)
    bot_config = result.scalars().first()
    
    if not bot_config:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive bot token")
        
    bot_id = bot_config.bot_id
    
    member_stmt = select(ChatMember).where(ChatMember.chat_id == payload.chat_id, ChatMember.user_id == bot_id)
    if not (await db.execute(member_stmt)).scalars().first():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bot is not a member of this chat")
        
    new_msg = Message(chat_id=payload.chat_id, sender_id=bot_id, text=payload.text)
    db.add(new_msg)
    
    chat_stmt = select(Chat).where(Chat.id == payload.chat_id)
    chat = (await db.execute(chat_stmt)).scalars().first()
    if chat: chat.updated_at = datetime.utcnow()
        
    await db.commit()
    await db.refresh(new_msg)
    
    created_iso = new_msg.created_at.isoformat()
    broadcast_payload = {
        "action": "new_message", "message_id": new_msg.id, "chat_id": payload.chat_id,
        "sender_id": bot_id, "text": payload.text, "attachment": None, "created_at": created_iso
    }
    
    members_stmt = select(ChatMember.user_id).where(ChatMember.chat_id == payload.chat_id)
    chat_members = (await db.execute(members_stmt)).scalars().all()
          
    receivers_ids = [m for m in chat_members if m != bot_id]
    
    for member_id in receivers_ids:
        await manager.send_personal_message(broadcast_payload, member_id)
            
    if receivers_ids:
        bot_user = (await db.execute(select(User.name, User.username).where(User.id == bot_id))).first()
        bot_name = bot_user.name or bot_user.username if bot_user else "Бот"

        devices_stmt = select(DeviceSession.push_token).where(
            DeviceSession.user_id.in_(receivers_ids), DeviceSession.is_active == True, DeviceSession.push_token.isnot(None)
        )
        tokens = (await db.execute(devices_stmt)).scalars().all()
        
        if tokens:
            send_push_notification.delay(
                tokens=list(tokens), title=bot_name, body=payload.text,
                data={"chat_id": payload.chat_id, "message_id": new_msg.id}
            )

    return new_msg