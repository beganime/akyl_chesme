from fastapi import APIRouter, Header, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime

from app.db.session import get_db
from app.models.bot import BotConfig
from app.models.message import Message
from app.models.chat import Chat, ChatMember
from app.schemas.chat import MessageResponse
from app.services.ws_manager import manager

from app.models.device import DeviceSession
from app.models.user import User
from app.tasks.push_tasks import send_push_notification

router = APIRouter()

class BotMessageRequest(BaseModel):
    chat_id: str
    text: str

@router.post("/sendMessage", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def bot_send_message(
    payload: BotMessageRequest,
    x_bot_token: str = Header(..., description="API токен бота (например 12345:ABC...)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Эндпоинт для сторонних ботов. Позволяет отправить сообщение в чат по API токену.
    """
    # 1. Проверяем валидность токена бота
    stmt = select(BotConfig).where(
        BotConfig.api_token == x_bot_token, 
        BotConfig.is_active == True
    )
    result = await db.execute(stmt)
    bot_config = result.scalars().first()
    
    if not bot_config:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid or inactive bot token"
        )
        
    bot_id = bot_config.bot_id
    
    # 2. Проверяем, состоит ли бот в указанном чате
    member_stmt = select(ChatMember).where(
        ChatMember.chat_id == payload.chat_id, 
        ChatMember.user_id == bot_id
    )
    if not (await db.execute(member_stmt)).scalars().first():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Bot is not a member of this chat"
        )
        
    # 3. Сохраняем сообщение бота в БД
    new_msg = Message(
        chat_id=payload.chat_id, 
        sender_id=bot_id, 
        text=payload.text
    )
    db.add(new_msg)
    
    # Обновляем время активности чата
    chat_stmt = select(Chat).where(Chat.id == payload.chat_id)
    chat = (await db.execute(chat_stmt)).scalars().first()
    if chat:
        chat.updated_at = datetime.utcnow()
        
    await db.commit()
    await db.refresh(new_msg)
    
    # 4. Рассылаем сообщение через Межсерверную шину (Redis Pub/Sub)
    created_iso = new_msg.created_at.isoformat()
    broadcast_payload = {
        "action": "new_message",
        "message_id": new_msg.id,
        "chat_id": payload.chat_id,
        "sender_id": bot_id,
        "text": payload.text,
        "attachment": None,
        "created_at": created_iso
    }
    
    # Ищем всех участников чата, чтобы доставить им сообщение
    members_stmt = select(ChatMember.user_id).where(ChatMember.chat_id == payload.chat_id)
    chat_members = (await db.execute(members_stmt)).scalars().all()
          
    receivers_ids = [m for m in chat_members if m != bot_id]
    
    for member_id in receivers_ids:
        # manager.send_personal_message сам закинет в Redis, и нужный воркер отдаст в WS
        await manager.send_personal_message(broadcast_payload, member_id)
            
    # --- НОВОЕ: Отправка PUSH от лица бота ---
    if receivers_ids:
        bot_user = (await db.execute(select(User.name, User.username).where(User.id == bot_id))).first()
        bot_name = bot_user.name or bot_user.username if bot_user else "Бот"

        devices_stmt = select(DeviceSession.push_token).where(
            DeviceSession.user_id.in_(receivers_ids),
            DeviceSession.is_active == True,
            DeviceSession.push_token.isnot(None)
        )
        tokens = (await db.execute(devices_stmt)).scalars().all()
        
        if tokens:
            send_push_notification.delay(
                tokens=list(tokens),
                title=bot_name,
                body=payload.text,
                data={"chat_id": payload.chat_id, "message_id": new_msg.id}
            )

    return new_msg