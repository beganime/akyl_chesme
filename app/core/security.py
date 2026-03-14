from datetime import datetime, timedelta
from typing import Any, Union
import bcrypt
from jose import jwt

from app.core.config import settings

# Определение алгоритма для JWT
ALGORITHM = "HS256"


def get_password_hash(password: str) -> str:
    """
    Хэширует пароль перед сохранением в базу данных.
    Используется нативный bcrypt для высокой производительности и безопасности.
    """
    # bcrypt требует байтовые строки
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    
    # Возвращаем обычную строку для корректного сохранения в PostgreSQL
    return hashed_password.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет, совпадает ли введенный пароль с хэшем из БД.
    """
    password_byte_enc = plain_password.encode('utf-8')
    hashed_password_byte_enc = hashed_password.encode('utf-8')
    
    return bcrypt.checkpw(password_byte_enc, hashed_password_byte_enc)


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