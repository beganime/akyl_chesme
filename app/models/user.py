from sqlalchemy import Column, String, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base import Base
# Импортируем готовые функции из нашего security-модуля
from app.core.security import get_password_hash, verify_password as verify_hash

class User(Base):
    __tablename__ = "users"

    # Поля из ERD
    username = Column(String, unique=True, index=True, nullable=False)
    is_bot = Column(Boolean, default=False, index=True)
    email = Column(String, nullable=True) # Nullable для ботов
    hashed_password = Column(String, nullable=True) # Nullable для ботов
    avatar_url = Column(String, nullable=True)
    name = Column(String, nullable=True, index=True)
    
    # Связи
    device_sessions = relationship("DeviceSession", back_populates="user", cascade="all, delete-orphan")
    bot_config = relationship("BotConfig", back_populates="user", uselist=False, cascade="all, delete-orphan")
    memberships = relationship("ChatMember", back_populates="user", cascade="all, delete-orphan")
    contacts_owned = relationship("Contact", back_populates="owner", foreign_keys="Contact.owner_id", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def set_password(self, password: str):
        """Хеширует и устанавливает пароль"""
        self.hashed_password = get_password_hash(password)

    def verify_password(self, password: str) -> bool:
        """Проверяет соответствие пароля хешу"""
        if not self.hashed_password:
            return False
        # Делегируем проверку централизованному методу
        return verify_hash(password, self.hashed_password)