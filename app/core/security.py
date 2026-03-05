from datetime import datetime, timedelta
from typing import Any, Union
from passlib.context import CryptContext
from jose import jwt

from app.core.config import settings

# Настройка passlib для хэширования паролей с использованием bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Определение алгоритма для JWT
ALGORITHM = "HS256"


def get_password_hash(password: str) -> str:
    """
    Хэширует пароль перед сохранением в базу данных.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет, совпадает ли введенный пароль с хэшем из БД.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta = None
) -> str:
    """
    Генерирует JWT токен доступа для авторизации.
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # Берем время жизни токена из настроек (по умолчанию 60 минут)
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    # Payload (полезная нагрузка) токена, где 'sub' (subject) - это обычно ID пользователя
    to_encode = {"exp": expire, "sub": str(subject)}
    
    # Создаем и подписываем токен нашим секретным ключом
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt