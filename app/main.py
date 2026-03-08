# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.v1.router import api_router
from app.db.session import engine
from app.db.base import Base
from app.core.firebase import init_firebase # Импорт Firebase
from app.services.ws_manager import manager # Добавим задел на 3 этап

from app.models import *

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    init_firebase() # 1. Запускаем Firebase
    
    # 2. Инициализируем RabbitMQ (для Этапа 3)
    await manager.setup_rabbitmq()
    
    async with engine.begin() as conn:
        # 3. Создаем таблицы (в проде заменится на Alembic)
        await conn.run_sync(Base.metadata.create_all) 
    yield
    # --- SHUTDOWN ---
    if manager.rmq_connection:
        await manager.rmq_connection.close()
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Настройка CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Подключение API роутеров
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "akyl-chesme-backend"}