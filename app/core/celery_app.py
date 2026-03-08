from celery import Celery
from app.core.config import settings

# Если передан CELERY_BROKER_URL (например, из docker-compose), используем его, иначе RABBITMQ_URL
broker_url = settings.CELERY_BROKER_URL or settings.RABBITMQ_URL

# Инициализируем Celery: задачи летят через RabbitMQ, результаты хранятся в Redis
celery_app = Celery(
    "akyl_worker",
    broker=broker_url,
    backend=settings.REDIS_URL
)

# Настройки для стабильной работы под нагрузкой
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ashgabat",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30, 
)

celery_app.conf.task_routes = {
    "app.tasks.*": {"queue": "main-queue"}
}