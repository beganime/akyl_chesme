# app/api/v1/endpoints/chats.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, desc, func
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.db.session import get_db
from app.models.user import User
from app.models.chat import Chat, ChatMember, ChatType
from app.models.message import Message
from app.schemas.chat import ChatCreate
from app.api.deps import get_current_user

router = APIRouter()

# ── Схемы ответа ──────────────────────────────────────────────

class UserBriefResponse(BaseModel):
    id: str
    username: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_online: Optional[bool] = False
    is_bot: Optional[bool] = False
    model_config = ConfigDict(from_attributes=True)

class LastMessageResponse(BaseModel):
    id: str
    chat_id: str
    sender_id: str
    text: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ChatResponse(BaseModel):
    id: str
    type: ChatType
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    updated_at: datetime
    unread_count: int = 0
    members: List[UserBriefResponse] = []
    last_message: Optional[LastMessageResponse] = None
    model_config = ConfigDict(from_attributes=True)

# ── Вспомогательная функция сборки ответа ─────────────────────

async def build_chat_response(
    chat: Chat,
    current_user_id: str,
    db: AsyncSession
) -> dict:
    # Участники
    members_stmt = (
        select(User)
        .join(ChatMember, ChatMember.user_id == User.id)
        .where(ChatMember.chat_id == chat.id)
    )
    members_result = await db.execute(members_stmt)
    members = members_result.scalars().all()

    # Последнее сообщение
    last_msg_stmt = (
        select(Message)
        .where(Message.chat_id == chat.id)
        .order_by(desc(Message.created_at))
        .limit(1)
    )
    last_msg_result = await db.execute(last_msg_stmt)
    last_msg = last_msg_result.scalars().first()

    # Количество непрочитанных (сообщения не от текущего юзера после последнего прочитанного)
    # Упрощённый вариант: считаем все сообщения не от текущего пользователя за последние N
    unread_stmt = (
        select(func.count(Message.id))
        .where(
            and_(
                Message.chat_id == chat.id,
                Message.sender_id != current_user_id,
            )
        )
    )
    # Для простоты — unread = 0 (полная реализация требует last_read_msg)
    unread_count = 0

    return {
        "id": chat.id,
        "type": chat.type,
        "name": getattr(chat, "name", None),
        "avatar_url": getattr(chat, "avatar_url", None),
        "updated_at": chat.updated_at,
        "unread_count": unread_count,
        "members": [
            {
                "id": m.id,
                "username": m.username,
                "name": m.name,
                "avatar_url": m.avatar_url,
                "is_online": getattr(m, "is_online", False),
                "is_bot": m.is_bot,
            }
            for m in members
        ],
        "last_message": {
            "id": last_msg.id,
            "chat_id": last_msg.chat_id,
            "sender_id": last_msg.sender_id,
            "text": last_msg.text,
            "created_at": last_msg.created_at,
        } if last_msg else None,
    }

# ── Эндпоинты ─────────────────────────────────────────────────

@router.post("/", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
    chat_in: ChatCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создать новый чат (диалог)."""
    if chat_in.type == ChatType.dialog:
        if not chat_in.target_user_id:
            raise HTTPException(status_code=400, detail="target_user_id обязателен для диалога")
        if chat_in.target_user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Нельзя создать диалог с собой")

        # Проверяем существование целевого пользователя
        target_stmt = select(User).where(User.id == chat_in.target_user_id)
        target_user = (await db.execute(target_stmt)).scalars().first()
        if not target_user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Ищем существующий диалог между двумя пользователями
        existing_stmt = (
            select(Chat.id)
            .join(ChatMember, ChatMember.chat_id == Chat.id)
            .where(
                Chat.type == ChatType.dialog,
                ChatMember.user_id.in_([current_user.id, chat_in.target_user_id])
            )
            .group_by(Chat.id)
            .having(func.count(ChatMember.user_id) == 2)
        )
        existing_id = (await db.execute(existing_stmt)).scalars().first()

        if existing_id:
            existing_chat = (await db.execute(
                select(Chat).where(Chat.id == existing_id)
            )).scalars().first()
            return await build_chat_response(existing_chat, current_user.id, db)

        # Создаём новый чат
        new_chat = Chat(type=ChatType.dialog)
        db.add(new_chat)
        await db.flush()

        db.add_all([
            ChatMember(chat_id=new_chat.id, user_id=current_user.id),
            ChatMember(chat_id=new_chat.id, user_id=chat_in.target_user_id),
        ])
        await db.commit()
        await db.refresh(new_chat)
        return await build_chat_response(new_chat, current_user.id, db)

    raise HTTPException(status_code=501, detail="Пока поддерживается только создание диалогов")


@router.get("/", response_model=List[ChatResponse])
async def get_my_chats(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список чатов текущего пользователя."""
    stmt = (
        select(Chat)
        .join(ChatMember, ChatMember.chat_id == Chat.id)
        .where(ChatMember.user_id == current_user.id)
        .order_by(desc(Chat.updated_at))
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    chats = result.scalars().all()

    responses = []
    for chat in chats:
        try:
            chat_data = await build_chat_response(chat, current_user.id, db)
            responses.append(chat_data)
        except Exception as e:
            # Не роняем весь список из-за одного сломанного чата
            import logging
            logging.getLogger(__name__).error(f"Error building chat {chat.id}: {e}")
            continue

    return responses


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
    chat_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить один чат по ID."""
    # Проверяем членство
    member_stmt = select(ChatMember).where(
        and_(ChatMember.chat_id == chat_id, ChatMember.user_id == current_user.id)
    )
    if not (await db.execute(member_stmt)).scalars().first():
        raise HTTPException(status_code=403, detail="Вы не состоите в этом чате")

    chat = (await db.execute(select(Chat).where(Chat.id == chat_id))).scalars().first()
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")

    return await build_chat_response(chat, current_user.id, db)


@router.get("/{chat_id}/messages")
async def get_chat_messages(
    chat_id: str,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить историю сообщений чата."""
    # Проверяем членство
    member_stmt = select(ChatMember).where(
        and_(ChatMember.chat_id == chat_id, ChatMember.user_id == current_user.id)
    )
    if not (await db.execute(member_stmt)).scalars().first():
        raise HTTPException(status_code=403, detail="Вы не состоите в этом чате")

    msg_stmt = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(desc(Message.created_at))
        .offset(skip)
        .limit(limit)
    )
    messages = (await db.execute(msg_stmt)).scalars().all()

    return [
        {
            "id": m.id,
            "chat_id": m.chat_id,
            "sender_id": m.sender_id,
            "text": m.text,
            "created_at": m.created_at.isoformat(),
            "status": "sent",
        }
        for m in messages
    ]