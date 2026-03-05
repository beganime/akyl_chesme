from sqlalchemy import Column, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base
import secrets

class BotConfig(Base):
    __tablename__ = "bot_configs"

    bot_id = Column(String, ForeignKey("users.id"), primary_key=True)
    # Генерация токена вида 12345:ABC-DEF...
    api_token = Column(String, unique=True, index=True, default=lambda: f"{secrets.randbelow(99999)}:{secrets.token_urlsafe(16)}")
    webhook_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    # Связь 1:1 с User
    user = relationship("User", back_populates="bot_config")