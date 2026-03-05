from pydantic import BaseModel, ConfigDict
from typing import Optional

class UserCreate(BaseModel):
    username: str
    password: str
    name: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    username: str
    is_bot: bool
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    
    # Позволяет Pydantic читать данные из моделей SQLAlchemy
    model_config = ConfigDict(from_attributes=True)