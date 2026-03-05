from sqlalchemy import Column, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base

class UserSettings(Base):
    __tablename__ = "user_settings"

    # PK одновременно является FK к пользователю (Связь 1:1)
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    
    push_enabled = Column(Boolean, default=True)
    theme_pref = Column(String, default="system") # light, dark, system
    subscription_tier = Column(String, default="free") # free, premium
    
    # Индекс для быстрого поиска при приглашении друзей
    referral_code = Column(String, unique=True, index=True, nullable=True)

    user = relationship("User", back_populates="settings")