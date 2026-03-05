from sqlalchemy import Column, String, ForeignKey, Text, Integer
from sqlalchemy.orm import relationship
from app.db.base import Base

class Message(Base):
    __tablename__ = "messages"

    chat_id = Column(String, ForeignKey("chats.id"), index=True, nullable=False)
    sender_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    
    # Позже для полнотекстового поиска добавим сюда GIN индекс
    text = Column(Text, nullable=True)

    # Связи
    chat = relationship("Chat", back_populates="messages")
    sender = relationship("User")
    attachments = relationship("Attachment", back_populates="message", cascade="all, delete-orphan")


class Attachment(Base):
    """Медиа, Файлы, Голосовые"""
    __tablename__ = "attachments"

    message_id = Column(String, ForeignKey("messages.id"), index=True, nullable=False)
    file_url = Column(String, nullable=False) # Ссылка на S3
    file_type = Column(String, nullable=False) # image, video, audio, document
    file_size = Column(Integer, nullable=True) # Размер в байтах (для управления кэшем на мобилке)

    message = relationship("Message", back_populates="attachments")