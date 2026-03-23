# app/models/chat.py
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

    type = Column(Enum(ChatType, native_enum=False), nullable=False, index=True)
    
    # Поля для группового чата / имени
    name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    # Связи
    members = relationship("ChatMember", back_populates="chat", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")


class ChatMember(Base):
    __tablename__ = "chat_members"

    chat_id = Column(String, ForeignKey("chats.id"), index=True, nullable=False)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    last_read_msg = Column(String, ForeignKey("messages.id", use_alter=True), nullable=True)

    # Связи
    chat = relationship("Chat", back_populates="members")
    user = relationship("User", back_populates="memberships")