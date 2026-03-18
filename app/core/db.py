from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Для 100k+ MAU мы ОБЯЗАТЕЛЬНО используем PgBouncer (pool_mode=transaction).
# Поэтому на уровне SQLAlchemy мы отключаем локальный пул (NullPool) и кэширование стейтментов.
engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=False,  # Строго False в проде
    connect_args={
        "prepared_statement_cache_size": 0, 
        "statement_cache_size": 0
    }
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)