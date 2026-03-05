from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from app.models.chat import ChatType

class ChatCreate(BaseModel):
    type: ChatType
    # Если создаем диалог, нужен ID собеседника (target_user_id)
    target_user_id: Optional[str] = None

class ChatResponse(BaseModel):
    id: str
    type: ChatType
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class MessageResponse(BaseModel):
    id: str
    chat_id: str
    sender_id: str
    text: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)