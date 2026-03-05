import json
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from jose import jwt, JWTError

from app.core.config import settings
from app.core.security import ALGORITHM
from app.schemas.token import TokenPayload
from app.db.session import async_session_maker
from app.services.ws_manager import manager
from app.models.message import Message, Attachment
from app.models.chat import Chat, ChatMember

router = APIRouter()

async def get_ws_current_user(token: str = Query(...)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)
        if token_data.sub is None: return None
        return token_data.sub
    except JWTError:
        return None

@router.websocket("/ws/chat")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str = Depends(get_ws_current_user)
):
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
                    local_id = payload.get("local_id") # Получаем локальный ID от мобилки
                    attachment_data = payload.get("attachment")
                    
                    if not chat_id: continue
                        
                    async with async_session_maker() as session:
                        # 1. Проверяем права участника
                        member_stmt = select(ChatMember).where(
                            ChatMember.chat_id == chat_id, ChatMember.user_id == user_id
                        )
                        if not (await session.execute(member_stmt)).scalars().first():
                            continue
                            
                        # 2. Сохраняем сообщение
                        new_msg = Message(chat_id=chat_id, sender_id=user_id, text=text)
                        session.add(new_msg)
                        await session.flush() # Получаем new_msg.id до коммита
                        
                        # 3. Прикрепляем файл (если есть)
                        if attachment_data:
                            new_attachment = Attachment(
                                message_id=new_msg.id,
                                file_url=attachment_data.get("file_url"),
                                file_type=attachment_data.get("file_type", "image")
                            )
                            session.add(new_attachment)
                            
                        # 4. Обновляем время чата
                        chat_stmt = update(Chat).where(Chat.id == chat_id).values(updated_at=datetime.utcnow())
                        await session.execute(chat_stmt)
                        
                        await session.commit()
                        await session.refresh(new_msg)
                        
                        # ================= РАССЫЛКА =================
                        created_iso = new_msg.created_at.isoformat()
                        
                        # 5. Отправляем ACK (подтверждение) ОТПРАВИТЕЛЮ
                        if local_id:
                            ack_payload = {
                                "action": "message_ack",
                                "local_id": local_id,
                                "server_msg_id": new_msg.id,
                                "created_at": created_iso
                            }
                            await manager.send_personal_message(ack_payload, user_id)
                        
                        # 6. Отправляем само сообщение ВСЕМ ОСТАЛЬНЫМ участникам
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
                        
                        for member_id in chat_members:
                            if member_id != user_id: # Отправителю уже ушел ACK, ему дублировать не надо
                                await manager.send_personal_message(broadcast_payload, member_id)
                                
            except json.JSONDecodeError:
                pass # Игнорируем кривой JSON
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)