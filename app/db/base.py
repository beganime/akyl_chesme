from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, DateTime, String, func # Добавили String
from app.utils.uuid_helper import generate_uuid7, generate_uuid4

class Base(DeclarativeBase):
    # Для сущностей, где важна сортировка по времени (сообщения)
    # Используем String вместо str!
    id = Column(String, primary_key=True, default=generate_uuid7, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}