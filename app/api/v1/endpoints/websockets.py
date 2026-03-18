import json
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from jose import jwt, JWTError
import logging

from app.core.config import settings
from app.core.security import ALGORITHM
from app.schemas.token import TokenPayload
# Исправленный импорт единого пула:
from app.core.db import AsyncSessionLocal 
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
async def websocket_endpoint(websocket: WebSocket, user_id: str = Depends(get_ws_current_user)):
    if not user_id:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, user_id)

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
                    
                    if not chat_id: continue
                        
                    # Оборачиваем работу с БД в try/except, чтобы сокет не умер при ошибке SQL
                    try:
                        async with AsyncSessionLocal() as session:
                            member_stmt = select(ChatMember).where(
                                ChatMember.chat_id == chat_id, ChatMember.user_id == user_id
                            )
                            if not (await session.execute(member_stmt)).scalars().first():
                                continue
                                
                            new_msg = Message(chat_id=chat_id, sender_id=user_id, text=text)
                            session.add(new_msg)
                            await session.flush() 
                            
                            if attachment_data:
                                new_attachment = Attachment(
                                    message_id=new_msg.id,
                                    file_url=attachment_data.get("file_url"),
                                    file_type=attachment_data.get("file_type", "image")
                                )
                                session.add(new_attachment)
                                
                            chat_stmt = update(Chat).where(Chat.id == chat_id).values(updated_at=datetime.utcnow())
                            await session.execute(chat_stmt)
                            await session.commit()
                            await session.refresh(new_msg)
                            
                            created_iso = new_msg.created_at.isoformat()
                            
                            if local_id:
                                ack_payload = {
                                    "action": "message_ack",
                                    "local_id": local_id,
                                    "server_msg_id": new_msg.id,
                                    "created_at": created_iso
                                }
                                await manager.send_personal_message(ack_payload, user_id)
                            
                            members_stmt = select(ChatMember.user_id).where(ChatMember.chat_id == chat_id)
                            chat_members = (await session.execute(members_stmt)).scalars().all()
                            
                            broadcast_payload = {
                                "action": "new_message",
                                "message_id": new_msg.id,
                                "chat_id": chat_id,
                                "sender_id": user_id,
                                "text": text,
                                "attachment": attachment_data,
                                "created_at": created_iso
                            }
                            
                            receivers_ids = [m_id for m_id in chat_members if m_id != user_id]
                            
                            for member_id in receivers_ids:
                                await manager.send_personal_message(broadcast_payload, member_id)

                            if receivers_ids:
                                sender_stmt = select(User.name, User.username).where(User.id == user_id)
                                sender = (await session.execute(sender_stmt)).first()
                                sender_name = sender.name or sender.username if sender else "Akyl Chesme"

                                devices_stmt = select(DeviceSession.push_token).where(
                                    DeviceSession.user_id.in_(receivers_ids),
                                    DeviceSession.is_active == True,
                                    DeviceSession.push_token.isnot(None)
                                )
                                tokens = (await session.execute(devices_stmt)).scalars().all()
                                
                                if tokens:
                                    push_body = text if text else "📷 Прикреплен файл"
                                    send_push_notification.delay(
                                        tokens=list(tokens), 
                                        title=f"Новое сообщение от {sender_name}", 
                                        body=push_body,
                                        data={"chat_id": chat_id, "message_id": new_msg.id}
                                    )
                                    
                            bot_stmt = select(BotConfig.webhook_url, BotConfig.bot_id).where(
                                BotConfig.bot_id.in_(chat_members),
                                BotConfig.is_active == True,
                                BotConfig.webhook_url.isnot(None)
                            )
                            bots = (await session.execute(bot_stmt)).all()
                            
                            for webhook_url, b_id in bots:
                                if b_id != user_id: 
                                    webhook_payload = {
                                        "update_type": "message",
                                        "message": {
                                            "message_id": new_msg.id,
                                            "chat_id": chat_id,
                                            "sender_id": user_id,
                                            "text": text,
                                            "created_at": created_iso
                                        }
                                    }
                                    dispatch_webhook.delay(webhook_url, webhook_payload)
                                    
                    except Exception as db_exc:
                        logger.error(f"Database error in websocket loop: {db_exc}")
                        # Мы перехватили ошибку БД. Сокет не умрет, юзер сможет отправить следующее сообщение.

            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)