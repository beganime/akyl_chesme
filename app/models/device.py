from sqlalchemy import Column, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base

class DeviceSession(Base):
    __tablename__ = "device_sessions"

    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    refresh_token_hash = Column(String, unique=True, index=True, nullable=False)
    device_name = Column(String, nullable=True) # Например "iPhone 15"
    push_token = Column(String, nullable=True, index=True) # FCM/APNs token
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="device_sessions")