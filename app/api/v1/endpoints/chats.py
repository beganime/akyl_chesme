from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, and_
from typing import List

from app.db.session import get_db
from app.models.user import User
from app.models.chat import Chat, ChatMember, ChatType
from app.models.message import Message
from app.schemas.chat import ChatCreate, ChatResponse, MessageResponse
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
    chat_in: ChatCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создать новый чат (диалог)."""
    if chat_in.type == ChatType.dialog:
        if not chat_in.target_user_id:
            raise HTTPException(status_code=400, detail="target_user_id is required for dialog")
        if chat_in.target_user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot create dialog with yourself")
            
        # Создаем сам чат
        new_chat = Chat(type=ChatType.dialog)
        db.add(new_chat)
        await db.flush() # Получаем ID чата без коммита
        
        # Добавляем участников (себя и собеседника)
        member1 = ChatMember(chat_id=new_chat.id, user_id=current_user.id)
        member2 = ChatMember(chat_id=new_chat.id, user_id=chat_in.target_user_id)
        db.add_all([member1, member2])
        
        await db.commit()
        await db.refresh(new_chat)
        return new_chat
    
    raise HTTPException(status_code=501, detail="Only dialog creation is supported right now")

@router.get("/", response_model=List[ChatResponse])
async def get_my_chats(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список чатов текущего пользователя (для главного экрана приложения)."""
    # Ищем все ChatMember для текущего юзера, джоиним Chat и сортируем по updated_at
    stmt = (
        select(Chat)
        .join(ChatMember)
        .where(ChatMember.user_id == current_user.id)
        .order_by(desc(Chat.updated_at))
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
    
@router.get("/{chat_id}/messages", response_model=List[MessageResponse])
async def get_chat_messages(
    chat_id: str,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить историю сообщений конкретного чата."""
    # Проверяем, состоит ли юзер в этом чате
    member_stmt = select(ChatMember).where(
        and_(ChatMember.chat_id == chat_id, ChatMember.user_id == current_user.id)
    )
    member_result = await db.execute(member_stmt)
    if not member_result.scalars().first():
        raise HTTPException(status_code=403, detail="You are not a member of this chat")
        
    # Достаем сообщения по убыванию даты (пагинация)
    msg_stmt = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(desc(Message.created_at))
        .offset(skip)
        .limit(limit)
    )
    msg_result = await db.execute(msg_stmt)
    return msg_result.scalars().all()