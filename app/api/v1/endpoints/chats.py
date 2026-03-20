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
from app.schemas.chat import ChatCreate, ChatResponse, MessageResponse, UserBriefResponse, AttachmentResponse
from app.api.deps import get_current_user

router = APIRouter()


async def build_chat_response(chat: Chat, current_user_id: str, db: AsyncSession) -> Dict[str, Any]:
    """Собирает полный ответ чата: участники, последнее сообщение, unread_count."""

    # Участники чата с их данными
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
    last_msg = (await db.execute(last_msg_stmt)).scalars().first()

    last_message_data = None
    if last_msg:
        # Sender последнего сообщения
        sender = next((m for m in members if m.id == last_msg.sender_id), None)
        # Вложения последнего сообщения
        attachments_stmt = select(Attachment).where(Attachment.message_id == last_msg.id)
        attachments = (await db.execute(attachments_stmt)).scalars().all()

        last_message_data = {
            "id": last_msg.id,
            "chat_id": last_msg.chat_id,
            "sender_id": last_msg.sender_id,
            "text": last_msg.text,
            "created_at": last_msg.created_at,
            "sender": {
                "id": sender.id,
                "username": sender.username,
                "name": sender.name,
                "avatar_url": sender.avatar_url,
                "is_online": sender.is_online or False,
                "is_bot": sender.is_bot,
            } if sender else None,
            "attachments": [
                {"file_url": a.file_url, "file_type": a.file_type, "file_size": a.file_size}
                for a in attachments
            ],
        }

    # Unread count: сообщения после last_read_msg текущего пользователя
    member_record_stmt = select(ChatMember).where(
        and_(ChatMember.chat_id == chat.id, ChatMember.user_id == current_user_id)
    )
    member_record = (await db.execute(member_record_stmt)).scalars().first()

    unread_count = 0
    if member_record and member_record.last_read_msg:
        # Считаем сообщения после прочитанного
        last_read_time_stmt = select(Message.created_at).where(Message.id == member_record.last_read_msg)
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
    elif member_record and not member_record.last_read_msg:
        # Ни одного сообщения не читали — все непрочитаны
        count_stmt = select(func.count()).where(
            and_(Message.chat_id == chat.id, Message.sender_id != current_user_id)
        )
        unread_count = (await db.execute(count_stmt)).scalar() or 0

    return {
        "id": chat.id,
        "type": chat.type,
        "name": chat.name,
        "avatar_url": chat.avatar_url,
        "updated_at": chat.updated_at,
        "unread_count": unread_count,
        "members": [
            {
                "id": m.id,
                "username": m.username,
                "name": m.name,
                "avatar_url": m.avatar_url,
                "is_online": m.is_online or False,
                "is_bot": m.is_bot,
            }
            for m in members
        ],
        "last_message": last_message_data,
    }


@router.post("/", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
    chat_in: ChatCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать новый чат (диалог)."""
    if chat_in.type == ChatType.dialog:
        if not chat_in.target_user_id:
            raise HTTPException(status_code=400, detail="target_user_id is required for dialog")
        if chat_in.target_user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot create dialog with yourself")

        target_user = (await db.execute(select(User).where(User.id == chat_in.target_user_id))).scalars().first()
        if not target_user:
            raise HTTPException(status_code=404, detail="Target user not found")

        # Проверяем существующий диалог между двумя пользователями
        existing_stmt = (
            select(Chat.id)
            .join(ChatMember, ChatMember.chat_id == Chat.id)
            .where(Chat.type == ChatType.dialog, ChatMember.user_id.in_([current_user.id, chat_in.target_user_id]))
            .group_by(Chat.id)
            .having(func.count(ChatMember.user_id) == 2)
        )
        existing_chat_id = (await db.execute(existing_stmt)).scalars().first()
        if existing_chat_id:
            existing_chat = (await db.execute(select(Chat).where(Chat.id == existing_chat_id))).scalars().first()
            return await build_chat_response(existing_chat, current_user.id, db)

        # Создаём чат
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

    raise HTTPException(status_code=501, detail="Only dialog creation is supported right now")


@router.get("/", response_model=List[ChatResponse])
async def get_my_chats(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    chats = result.scalars().unique().all()

    # Собираем полные данные для каждого чата
    response = []
    for chat in chats:
        chat_data = await build_chat_response(chat, current_user.id, db)
        response.append(chat_data)

    return response


@router.get("/{chat_id}/messages", response_model=List[MessageResponse])
async def get_chat_messages(
    chat_id: str,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить историю сообщений чата."""
    # Проверяем членство
    member_stmt = select(ChatMember).where(
        and_(ChatMember.chat_id == chat_id, ChatMember.user_id == current_user.id)
    )
    if not (await db.execute(member_stmt)).scalars().first():
        raise HTTPException(status_code=403, detail="You are not a member of this chat")

    # Сообщения с sender и attachments
    msg_stmt = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(desc(Message.created_at))
        .offset(skip)
        .limit(limit)
    )
    messages = (await db.execute(msg_stmt)).scalars().all()

    result = []
    for msg in messages:
        sender = (await db.execute(select(User).where(User.id == msg.sender_id))).scalars().first()
        attachments = (await db.execute(select(Attachment).where(Attachment.message_id == msg.id))).scalars().all()
        result.append({
            "id": msg.id,
            "chat_id": msg.chat_id,
            "sender_id": msg.sender_id,
            "text": msg.text,
            "created_at": msg.created_at,
            "sender": {
                "id": sender.id,
                "username": sender.username,
                "name": sender.name,
                "avatar_url": sender.avatar_url,
                "is_online": sender.is_online or False,
                "is_bot": sender.is_bot,
            } if sender else None,
            "attachments": [
                {"file_url": a.file_url, "file_type": a.file_type, "file_size": a.file_size}
                for a in attachments
            ],
        })

    return result