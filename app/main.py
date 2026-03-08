# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.v1.router import api_router
from app.db.session import engine
from app.core.firebase import init_firebase
from app.services.ws_manager import manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    init_firebase() # 1. Запускаем Firebase
    
    # 2. Инициализируем RabbitMQ (для Этапа 3 и 4)
    await manager.setup_rabbitmq()
    
    # ВНИМАНИЕ: Мы удалили Base.metadata.create_all
    # Теперь структура таблиц управляется ИСКЛЮЧИТЕЛЬНО через Alembic миграции!
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