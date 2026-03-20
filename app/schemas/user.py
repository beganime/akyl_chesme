from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    name: Optional[str] = Field(default=None, max_length=128)


class UserResponse(BaseModel):
    id: str
    username: str
    is_bot: bool
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_online: bool = False
    last_seen: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)