import os
import logging
import firebase_admin
from firebase_admin import credentials
from app.core.config import settings

logger = logging.getLogger(__name__)

def init_firebase():
    """Инициализация Firebase Admin SDK (вызывается один раз)."""
    if not settings.FIREBASE_CREDENTIALS_PATH:
        logger.warning("FIREBASE_CREDENTIALS_PATH не задан. Пуши работать не будут.")
        return

    if not os.path.exists(settings.FIREBASE_CREDENTIALS_PATH):
        logger.warning(f"Файл ключей Firebase не найден по пути: {settings.FIREBASE_CREDENTIALS_PATH}")
        return

    try:
        # Проверяем, не инициализировано ли приложение ранее (важно для горячих перезагрузок)
        firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK успешно инициализирован.")