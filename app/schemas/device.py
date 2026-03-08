from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class DeviceCreate(BaseModel):
    push_token: str
    device_name: Optional[str] = "Unknown Device"
    location: Optional[str] = None # Приложение может передать гео-позицию (город/страну)

class DeviceResponse(BaseModel):
    id: str
    device_name: Optional[str]
    push_token: Optional[str]
    ip_address: Optional[str]
    location: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)