import ssl
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# Настраиваем кэширование (ОБЯЗАТЕЛЬНО для производительности, раз локального пулера больше нет)
connect_args = {
    "prepared_statement_cache_size": 100, 
    "statement_cache_size": 100
}

# Если облако требует SSL, добавляем контекст
if settings.POSTGRES_SSL_REQUIRE:
    # Отключаем строгую проверку hostname, так как подключаемся по IP (стандарт для Managed DB)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ssl_context

# Используем внутренний пул SQLAlchemy (NullPool удален)
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=40,          # Базовое количество соединений
    max_overflow=60,       # Запасные соединения при пиках (суммарно до 100)
    pool_timeout=30,
    pool_recycle=1800,     # Обновлять соединения каждые 30 мин (защита от дисконнектов в облаке)
    echo=False,            # Строго False в проде
    connect_args=connect_args
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)