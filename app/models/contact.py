from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class Contact(Base):
    __tablename__ = "contacts"

    owner_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    contact_user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    
    # Как пользователь записал друга у себя
    saved_name = Column(String, nullable=False)

    # Связи (foreign_keys нужны, так как обе колонки ссылаются на таблицу users)
    owner = relationship("User", foreign_keys=[owner_id], back_populates="contacts_owned")
    contact_user = relationship("User", foreign_keys=[contact_user_id])