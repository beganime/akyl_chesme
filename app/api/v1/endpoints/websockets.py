import asyncio
import json
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, and_
from jose import jwt, JWTError
import logging

from app.core.config import settings
from app.core.security import ALGORITHM
from app.schemas.token import TokenPayload
from app.db.session import async_session_maker  # Единый session maker, не из core/db
from app.services.ws_manager import manager
from app.models.message import Message, Attachment
from app.models.chat import Chat, ChatMember
from app.models.bot import BotConfig
from app.tasks.bot_tasks import dispatch_webhook
from app.models.device import DeviceSession
from app.models.user import User
from app.tasks.push_tasks import send_push_notification

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_ws_current_user(token: str = Query(...)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)
        return token_data.sub
    except JWTError:
        return None


@router.websocket("/ws/chat")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str = Depends(get_ws_current_user),
):
    if not user_id:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, user_id)

    # Обновляем is_online = True при подключении
    async with async_session_maker() as session:
        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_online=True)
        )
        await session.commit()

    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                action = payload.get("action")

                if action == "send_message":
                    chat_id = payload.get("chat_id")
                    text = payload.get("text")
                    local_id = payload.get("local_id")
                    attachment_data = payload.get("attachment")

                    if not chat_id:
                        continue

                    try:
                        async with async_session_maker() as session:
                            # Проверяем членство
                            member_stmt = select(ChatMember).where(
                                and_(ChatMember.chat_id == chat_id, ChatMember.user_id == user_id)
                            )
                            if not (await session.execute(member_stmt)).scalars().first():
                                continue

                            # Создаём сообщение
                            new_msg = Message(chat_id=chat_id, sender_id=user_id, text=text)
                            session.add(new_msg)
                            await session.flush()

                            # Вложение
                            if attachment_data:
                                new_attachment = Attachment(
                                    message_id=new_msg.id,
                                    file_url=attachment_data.get("url") or attachment_data.get("file_url", ""),
                                    file_type=attachment_data.get("type") or attachment_data.get("file_type", "image"),
                                    file_size=attachment_data.get("size"),
                                )
                                session.add(new_attachment)

                            # Обновляем updated_at чата
                            await session.execute(
                                update(Chat)
                                .where(Chat.id == chat_id)
                                .values(updated_at=datetime.now(timezone.utc))
                            )
                            await session.commit()
                            await session.refresh(new_msg)

                            created_iso = new_msg.created_at.isoformat()

                            # ACK отправителю
                            if local_id:
                                await manager.send_personal_message({
                                    "action": "message_ack",
                                    "local_id": local_id,
                                    "server_msg_id": new_msg.id,
                                    "created_at": created_iso,
                                }, user_id)

                            # Данные отправителя для broadcast
                            sender_stmt = select(User).where(User.id == user_id)
                            sender = (await session.execute(sender_stmt)).scalars().first()
                            sender_name = (sender.name or sender.username) if sender else "AkylChat"

                            # Все участники чата
                            members_stmt = select(ChatMember.user_id).where(ChatMember.chat_id == chat_id)
                            chat_members = (await session.execute(members_stmt)).scalars().all()
                            receivers_ids = [m for m in chat_members if m != user_id]

                            # Broadcast другим участникам
                            broadcast_payload = {
                                "action": "new_message",
                                "message_id": new_msg.id,
                                "chat_id": chat_id,
                                "sender_id": user_id,
                                "sender": {
                                    "id": sender.id,
                                    "name": sender.name,
                                    "username": sender.username,
                                    "avatar_url": sender.avatar_url,
                                } if sender else None,
                                "text": text,
                                "attachment": attachment_data,
                                "created_at": created_iso,
                            }

                            if receivers_ids:
                                await asyncio.gather(*(
                                    manager.send_personal_message(broadcast_payload, member_id)
                                    for member_id in receivers_ids
                                ))

                            # Push уведомления
                            if receivers_ids:
                                devices_stmt = select(DeviceSession.push_token).where(
                                    DeviceSession.user_id.in_(receivers_ids),
                                    DeviceSession.is_active.is_(True),
                                    DeviceSession.push_token.isnot(None),
                                )
                                tokens = (await session.execute(devices_stmt)).scalars().all()

                                if tokens:
                                    push_body = text if text else "📎 Вложение"
                                    send_push_notification.delay(
                                        tokens=list(tokens),
                                        title=sender_name,
                                        body=push_body,
                                        data={
                                            "chat_id": chat_id,
                                            "message_id": new_msg.id,
                                            # chat_title нужен клиенту для навигации
                                            "chat_title": sender_name,
                                            "avatar_url": sender.avatar_url or "" if sender else "",
                                        },
                                    )

                            # Webhook для ботов
                            bot_stmt = select(BotConfig.webhook_url, BotConfig.bot_id).where(
                                BotConfig.bot_id.in_(chat_members),
                                BotConfig.is_active.is_(True),
                                BotConfig.webhook_url.isnot(None),
                            )
                            bots = (await session.execute(bot_stmt)).all()
                            for webhook_url, b_id in bots:
                                if b_id != user_id:
                                    dispatch_webhook.delay(webhook_url, {
                                        "update_type": "message",
                                        "message": {
                                            "message_id": new_msg.id,
                                            "chat_id": chat_id,
                                            "sender_id": user_id,
                                            "text": text,
                                            "created_at": created_iso,
                                        },
                                    })

                    except Exception as db_exc:
                        logger.error(f"DB error in websocket: {db_exc}", exc_info=True)

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)

        # Обновляем is_online = False и last_seen при отключении
        async with async_session_maker() as session:
            await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(is_online=False, last_seen=datetime.now(timezone.utc))
            )
            await session.commit()