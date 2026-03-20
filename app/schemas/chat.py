from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from app.models.chat import ChatType


# ── User brief (используется внутри чатов) ────────────────────────────────────
class UserBriefResponse(BaseModel):
    id: str
    username: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_online: bool = False
    is_bot: bool = False

    model_config = ConfigDict(from_attributes=True)


# ── Вложения ──────────────────────────────────────────────────────────────────
class AttachmentResponse(BaseModel):
    file_url: str
    file_type: str  # image, video, audio, document
    file_size: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# ── Сообщение ─────────────────────────────────────────────────────────────────
class MessageResponse(BaseModel):
    id: str
    chat_id: str
    sender_id: str
    text: Optional[str] = None
    created_at: datetime
    sender: Optional[UserBriefResponse] = None
    attachments: List[AttachmentResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ── Создание чата ─────────────────────────────────────────────────────────────
class ChatCreate(BaseModel):
    type: ChatType
    target_user_id: Optional[str] = None


# ── Ответ чата — полный, как ожидает клиент ───────────────────────────────────
class ChatResponse(BaseModel):
    id: str
    type: ChatType
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    updated_at: datetime
    unread_count: int = 0
    members: List[UserBriefResponse] = []
    last_message: Optional[MessageResponse] = None

    model_config = ConfigDict(from_attributes=True)