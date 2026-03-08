# app/db/session.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.core.config import settings

# 1. Отключаем pool_size и max_overflow (используем NullPool). Пулингом теперь занимается только PgBouncer.
# 2. Передаем prepared_statement_cache_size=0, иначе PgBouncer в режиме transaction сломает запросы.
engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool, 
    echo=False,      
    connect_args={
        "prepared_statement_cache_size": 0, 
        "statement_cache_size": 0
    }
)

async_session_maker = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()