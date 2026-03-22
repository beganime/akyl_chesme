# app/api/v1/endpoints/chats.py
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, desc, func
from sqlalchemy.orm import selectinload
from typing import List, Any, Dict

from app.db.session import get_db
from app.models.user import User
from app.models.chat import Chat, ChatMember, ChatType
from app.models.message import Message, Attachment
from app.schemas.chat import ChatCreate, ChatResponse, MessageResponse
from app.api.deps import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


async def build_chat_response(
    chat: Chat,
    current_user_id: str,
    db: AsyncSession,
) -> Dict[str, Any]:
    """Строим полный ответ чата — оптимизировано через join."""

    # Участники одним запросом
    members_stmt = (
        select(User)
        .join(ChatMember, ChatMember.user_id == User.id)
        .where(ChatMember.chat_id == chat.id)
    )
    members = (await db.execute(members_stmt)).scalars().all()

    # Последнее сообщение + вложения одним запросом
    last_msg_stmt = (
        select(Message)
        .where(Message.chat_id == chat.id)
        .order_by(desc(Message.created_at))
        .limit(1)
        .options(selectinload(Message.attachments))
    )
    last_msg = (await db.execute(last_msg_stmt)).scalars().first()

    last_message_data = None
    if last_msg:
        sender = next((m for m in members if m.id == last_msg.sender_id), None)
        last_message_data = {
            "id": last_msg.id,
            "chat_id": last_msg.chat_id,
            "sender_id": last_msg.sender_id,
            "text": last_msg.text,
            "created_at": last_msg.created_at,
            "sender": {
                "id": sender.id, "username": sender.username,
                "name": sender.name, "avatar_url": sender.avatar_url,
                "is_online": sender.is_online or False,
                "is_bot": sender.is_bot,
            } if sender else None,
            "attachments": [
                {"file_url": a.file_url, "file_type": a.file_type, "file_size": a.file_size}
                for a in last_msg.attachments
            ],
        }

    # Unread count
    member_record_stmt = select(ChatMember).where(
        and_(ChatMember.chat_id == chat.id, ChatMember.user_id == current_user_id)
    )
    member_record = (await db.execute(member_record_stmt)).scalars().first()

    unread_count = 0
    if member_record:
        if member_record.last_read_msg:
            last_read_time_stmt = select(Message.created_at).where(
                Message.id == member_record.last_read_msg
            )
            last_read_time = (await db.execute(last_read_time_stmt)).scalar()
            if last_read_time:
                unread_stmt = select(func.count()).where(
                    and_(
                        Message.chat_id == chat.id,
                        Message.created_at > last_read_time,
                        Message.sender_id != current_user_id,
                    )
                )
                unread_count = (await db.execute(unread_stmt)).scalar() or 0
        else:
            count_stmt = select(func.count()).where(
                and_(Message.chat_id == chat.id, Message.sender_id != current_user_id)
            )
            unread_count = (await db.execute(count_stmt)).scalar() or 0

    # target_user для диалога
    target_user = next((m for m in members if m.id != current_user_id), None) if chat.type == ChatType.dialog else None

    return {
        "id": chat.id,
        "type": chat.type,
        "name": chat.name or (target_user.name if target_user else None),
        "avatar_url": chat.avatar_url or (target_user.avatar_url if target_user else None),
        "updated_at": chat.updated_at,
        "unread_count": unread_count,
        "members": [
            {
                "id": m.id, "username": m.username, "name": m.name,
                "avatar_url": m.avatar_url, "is_online": m.is_online or False,
                "is_bot": m.is_bot,
            }
            for m in members
        ],
        "last_message": last_message_data,
        "target_user": {
            "id": target_user.id, "username": target_user.username,
            "name": target_user.name, "avatar_url": target_user.avatar_url,
            "is_online": target_user.is_online or False,
        } if target_user else None,
    }


@router.post("/", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
    chat_in: ChatCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if chat_in.type == ChatType.dialog:
        if not chat_in.target_user_id:
            raise HTTPException(status_code=400, detail="target_user_id обязателен для диалога")
        if chat_in.target_user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Нельзя создать диалог с собой")

        target_user = (
            await db.execute(select(User).where(User.id == chat_in.target_user_id))
        ).scalars().first()
        if not target_user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Проверяем существующий диалог
        existing_stmt = (
            select(Chat.id)
            .join(ChatMember, ChatMember.chat_id == Chat.id)
            .where(
                Chat.type == ChatType.dialog,
                ChatMember.user_id.in_([current_user.id, chat_in.target_user_id]),
            )
            .group_by(Chat.id)
            .having(func.count(ChatMember.user_id) == 2)
        )
        existing_id = (await db.execute(existing_stmt)).scalars().first()
        if existing_id:
            existing_chat = (
                await db.execute(select(Chat).where(Chat.id == existing_id))
            ).scalars().first()
            return await build_chat_response(existing_chat, current_user.id, db)

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

    raise HTTPException(status_code=501, detail="Только диалоги поддерживаются")


@router.get("/", response_model=List[ChatResponse])
async def get_my_chats(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(Chat)
        .join(ChatMember, ChatMember.chat_id == Chat.id)
        .where(ChatMember.user_id == current_user.id)
        .order_by(desc(Chat.updated_at))
        .offset(skip)
        .limit(limit)
    )
    chats = (await db.execute(stmt)).scalars().unique().all()

    result = []
    for chat in chats:
        try:
            chat_data = await build_chat_response(chat, current_user.id, db)
            result.append(chat_data)
        except Exception as e:
            logger.error(f"Error building chat response for {chat.id}: {e}")
    return result


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
    chat_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Проверяем членство
    member_stmt = select(ChatMember).where(
        and_(ChatMember.chat_id == chat_id, ChatMember.user_id == current_user.id)
    )
    if not (await db.execute(member_stmt)).scalars().first():
        raise HTTPException(status_code=403, detail="Вы не являетесь участником этого чата")

    chat = (await db.execute(select(Chat).where(Chat.id == chat_id))).scalars().first()
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")

    return await build_chat_response(chat, current_user.id, db)


@router.get("/{chat_id}/messages", response_model=List[MessageResponse])
async def get_chat_messages(
    chat_id: str,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Проверяем членство
    member_stmt = select(ChatMember).where(
        and_(ChatMember.chat_id == chat_id, ChatMember.user_id == current_user.id)
    )
    if not (await db.execute(member_stmt)).scalars().first():
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    # Загружаем сообщения с отправителями и вложениями за один раз
    msg_stmt = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(desc(Message.created_at))
        .offset(skip)
        .limit(min(limit, 100))  # Максимум 100
        .options(selectinload(Message.attachments))
    )
    messages = (await db.execute(msg_stmt)).scalars().all()

    # Загружаем отправителей пачкой
    sender_ids = list({m.sender_id for m in messages})
    senders_map: Dict[str, User] = {}
    if sender_ids:
        senders_result = await db.execute(
            select(User).where(User.id.in_(sender_ids))
        )
        senders_map = {u.id: u for u in senders_result.scalars().all()}

    result = []
    for msg in messages:
        sender = senders_map.get(msg.sender_id)
        result.append({
            "id": msg.id,
            "chat_id": msg.chat_id,
            "sender_id": msg.sender_id,
            "text": msg.text,
            "created_at": msg.created_at,
            "sender": {
                "id": sender.id, "username": sender.username,
                "name": sender.name, "avatar_url": sender.avatar_url,
                "is_online": sender.is_online or False,
                "is_bot": sender.is_bot,
            } if sender else None,
            "attachments": [
                {"file_url": a.file_url, "file_type": a.file_type, "file_size": a.file_size}
                for a in msg.attachments
            ],
        })

    return result