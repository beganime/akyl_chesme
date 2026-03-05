import enum
from sqlalchemy import Column, String, Enum, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from app.db.base import Base

class ChatType(str, enum.Enum):
    dialog = "dialog"
    group = "group"
    channel = "channel"
    bot = "bot"

class Chat(Base):
    __tablename__ = "chats"

    # Используем Enum на уровне БД (native_enum=False для универсальности)
    type = Column(Enum(ChatType, native_enum=False), nullable=False, index=True)
    
    # Переопределяем updated_at, чтобы повесить на него B-Tree индекс, 
    # как указано в ТЗ (для быстрой сортировки ленты чатов)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    # Связи
    members = relationship("ChatMember", back_populates="chat", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")


class ChatMember(Base):
    __tablename__ = "chat_members"

    chat_id = Column(String, ForeignKey("chats.id"), index=True, nullable=False)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    
    # ID последнего прочитанного сообщения (для быстрого подсчета unread_count)
    # use_alter=True помогает избежать циклических зависимостей при создании таблиц
    last_read_msg = Column(String, ForeignKey("messages.id", use_alter=True), nullable=True)

    # Связи
    chat = relationship("Chat", back_populates="members")
    user = relationship("User", back_populates="memberships")