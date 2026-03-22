# app/schemas/chat.py
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from app.models.chat import ChatType


class UserBriefResponse(BaseModel):
    id: str
    username: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_online: bool = False
    is_bot: bool = False
    last_seen: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class AttachmentResponse(BaseModel):
    file_url: str
    file_type: str
    file_size: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    id: str
    chat_id: str
    sender_id: str
    text: Optional[str] = None
    created_at: datetime
    sender: Optional[UserBriefResponse] = None
    attachments: List[AttachmentResponse] = []
    model_config = ConfigDict(from_attributes=True)


class ChatCreate(BaseModel):
    type: ChatType
    # Диалог
    target_user_id: Optional[str] = None
    # Группа
    name: Optional[str] = None
    member_ids: Optional[List[str]] = None
    avatar_url: Optional[str] = None


class ChatResponse(BaseModel):
    id: str
    type: ChatType
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    updated_at: datetime
    unread_count: int = 0
    members: List[UserBriefResponse] = []
    last_message: Optional[MessageResponse] = None
    target_user: Optional[UserBriefResponse] = None
    model_config = ConfigDict(from_attributes=True)