"""
Утилита для генерации UUID.
Приоритет: uuid7 (time-sortable) -> fallback на uuid4 + timestamp
"""
import uuid
import time
from typing import Union

try:
    from uuid7 import uuid7 as _uuid7
    UUID7_AVAILABLE = True
except ImportError:
    UUID7_AVAILABLE = False


def generate_uuid7() -> str:
    """
    Генерирует UUIDv7 (time-sortable) если доступен пакет uuid7,
    иначе fallback на uuid4 с префиксом timestamp для приблизительной сортировки.
    """
    if UUID7_AVAILABLE:
        return str(_uuid7())
    
    # Fallback: timestamp (ms) + uuid4
    # Формат: {timestamp_hex}-{uuid4_rest}
    timestamp_ms = int(time.time() * 1000)
    timestamp_hex = f"{timestamp_ms:012x}"
    uid = uuid.uuid4()
    # Заменяем первые 12 символов hex на timestamp
    uid_hex = f"{timestamp_hex}{str(uid)[12:]}"
    # Валидируем формат UUID (8-4-4-4-12)
    return f"{uid_hex[:8]}-{uid_hex[8:12]}-{uid_hex[12:16]}-{uid_hex[16:20]}-{uid_hex[20:]}"


def generate_uuid4() -> str:
    """Стандартный UUID v4 для случаев, где сортировка не критична."""
    return str(uuid.uuid4())