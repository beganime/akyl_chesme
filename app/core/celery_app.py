from celery import Celery
from app.core.config import settings

# Инициализируем Celery, используя Redis URL из наших настроек
celery_app = Celery(
    "akyl_worker",
    broker=settings.REDIS_URL,
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
    task_time_limit=30, # Жесткий лимит на выполнение задачи (чтобы зависшие боты не забили воркеры)
)

# Маршрутизация задач (на будущее, если будем бить на разные очереди)
celery_app.conf.task_routes = {
    "app.tasks.*": {"queue": "main-queue"}
}