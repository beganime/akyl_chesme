import secrets
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.db.session import get_db
from app.models.bot import BotConfig
from app.models.chat import Chat, ChatMember
from app.models.device import DeviceSession
from app.models.message import Message
from app.models.user import User
from app.schemas.chat import MessageResponse
from app.services.ws_manager import manager
from app.tasks.push_tasks import send_push_notification

router = APIRouter()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


async def verify_django_portal_key(api_key: str = Security(api_key_header)):
    if not secrets.compare_digest(api_key, settings.CORE_API_KEY):
        raise HTTPException(status_code=403, detail="Invalid CORE_API_KEY")
    return api_key


class BotRegisterDjangoRequest(BaseModel):
    bot_username: str
    name: str
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    webhook_url: HttpUrl
    commands: Optional[Dict[str, str]] = None
    developer_id: str
    developer_email: Optional[str] = None


@router.post("/bots", dependencies=[Depends(verify_django_portal_key)])
async def register_bot_from_django(
    payload: BotRegisterDjangoRequest, db: AsyncSession = Depends(get_db)
):
    stmt = select(User).where(User.username == payload.bot_username)
    if (await db.execute(stmt)).scalars().first():
        raise HTTPException(status_code=409, detail="Имя бота уже используется")

    new_bot_user = User(
        username=payload.bot_username,
        name=payload.name,
        avatar_url=payload.avatar_url,
        is_bot=True,
    )
    db.add(new_bot_user)
    await db.flush()

    generated_token = secrets.token_urlsafe(32)
    new_bot_config = BotConfig(
        bot_id=new_bot_user.id,
        api_token=generated_token,
        webhook_url=str(payload.webhook_url),
        is_active=True,
    )
    db.add(new_bot_config)
    await db.commit()

    return {
        "success": True,
        "message": "Бот успешно зарегистрирован",
        "data": {
            "bot": {
                "id": new_bot_user.id,
                "bot_username": new_bot_user.username,
                "status": "active",
            },
            "token": generated_token,
            "jwt_token": "not_required_for_bot_api",
            "deep_link": f"https://akyl-cheshmesi.ru/b/{new_bot_user.username}",
        },
    }


class BotMessageRequest(BaseModel):
    chat_id: str
    text: str


@router.post("/sendMessage", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def bot_send_message(
    payload: BotMessageRequest,
    x_bot_token: str = Header(..., description="API токен бота"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(BotConfig).where(BotConfig.api_token == x_bot_token, BotConfig.is_active.is_(True))
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
    if chat:
        chat.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(new_msg)

    created_iso = new_msg.created_at.isoformat()
    broadcast_payload: Dict[str, Any] = {
        "action": "new_message",
        "message_id": new_msg.id,
        "chat_id": payload.chat_id,
        "sender_id": bot_id,
        "text": payload.text,
        "attachment": None,
        "created_at": created_iso,
    }

    members_stmt = select(ChatMember.user_id).where(ChatMember.chat_id == payload.chat_id)
    chat_members = (await db.execute(members_stmt)).scalars().all()
    receivers_ids = [m for m in chat_members if m != bot_id]

    for member_id in receivers_ids:
        await manager.send_personal_message(broadcast_payload, member_id)

    if receivers_ids:
        bot_user = (await db.execute(select(User.name, User.username).where(User.id == bot_id))).first()
        bot_name = (bot_user.name or bot_user.username) if bot_user else "Бот"

        devices_stmt = select(DeviceSession.push_token).where(
            DeviceSession.user_id.in_(receivers_ids),
            DeviceSession.is_active.is_(True),
            DeviceSession.push_token.isnot(None),
        )
        tokens = (await db.execute(devices_stmt)).scalars().all()

        if tokens:
            send_push_notification.delay(
                tokens=list(tokens),
                title=bot_name,
                body=payload.text,
                data={"chat_id": payload.chat_id, "message_id": new_msg.id},
            )

    return new_msg
