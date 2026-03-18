from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# Исправлено имя переменной с URI на DATABASE_URL.
# Архитектурное примечание: так как мы используем PgBouncer (порт 6432),
# пулинг соединений будет происходить на стороне PgBouncer. 
# Тем не менее, локальный пул SQLAlchemy (pool_size=20) оставим для балансировки воркеров FastAPI.
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=50,
    pool_pre_ping=True,
    pool_timeout=30.0,
    echo=False,  # Обязательно False для продакшена
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)