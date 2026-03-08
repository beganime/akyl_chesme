import logging
from firebase_admin import messaging
from firebase_admin.exceptions import FirebaseError

from app.core.celery_app import celery_app
from app.core.firebase import init_firebase

logger = logging.getLogger(__name__)

# Инициализируем Firebase в воркере Celery при загрузке модуля
init_firebase()

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def send_push_notification(self, tokens: list[str], title: str, body: str, data: dict = None):
    """
    Фоновая задача для отправки FCM push-уведомлений на массив устройств.
    """
    if not tokens:
        return 0

    # Убираем дубликаты токенов, если есть
    tokens = list(set(tokens))
    
    # Формируем сообщение (Multicast для рассылки на несколько девайсов одного юзера)
    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        data=data if data else {}, # Скрытые данные (например, chat_id для перехода по клику)
        tokens=tokens,
    )

    try:
        response = messaging.send_each_for_multicast(message)
        logger.info(f"Push отправлен: {response.success_count} успешно, {response.failure_count} ошибок.")
        
        # По хорошему здесь можно обрабатывать response.responses и удалять из БД 
        # токены (DeviceSession), если они просрочены (NotRegistered), чтобы не спамить в будущем.
        
        return response.success_count
    except FirebaseError as exc:
        logger.error(f"Ошибка отправки FCM Push: {exc}")
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.error(f"Неожиданная ошибка при пушах: {exc}")
        # Если Firebase не настроен, просто игнорируем, чтобы задача не висела
        pass