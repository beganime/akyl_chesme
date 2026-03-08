import httpx
import logging
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def dispatch_webhook(self, webhook_url: str, payload: dict):
    """
    Фоновая задача для отправки сообщения на сервер стороннего бота.
    Если сервер бота отвечает ошибкой 5xx или недоступен, Celery автоматически
    повторит попытку до 3 раз с задержкой.
    """
    try:
        # Используем синхронный клиент httpx для воркера Celery
        with httpx.Client(timeout=10.0) as client:
            response = client.post(webhook_url, json=payload)
            response.raise_for_status()
            logger.info(f"Webhook успешно отправлен на {webhook_url}")
            return response.status_code
    except httpx.HTTPError as exc:
        logger.error(f"Ошибка отправки вебхука на {webhook_url}: {exc}")
        # Повторяем задачу при сбое сети или ошибке на стороне бота
        raise self.retry(exc=exc)