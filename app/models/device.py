import uuid
from sqlalchemy import Column, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base

class DeviceSession(Base):
    __tablename__ = "device_sessions"

    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    
    # Сделали nullable=True, чтобы легко привязывать устройства без сложной логики refresh-токенов
    refresh_token_hash = Column(String, unique=True, index=True, nullable=True) 
    
    device_name = Column(String, nullable=True) # Например "iPhone 15"
    push_token = Column(String, nullable=True, index=True) # FCM/APNs token
    
    # Новые поля для аналитики и безопасности
    ip_address = Column(String, nullable=True)
    location = Column(String, nullable=True) # Например: "Ashgabat, TM"
    
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="device_sessions")