import ssl
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings

# Те же настройки, что и в core/db.py для консистентности
connect_args = {
    "prepared_statement_cache_size": 100, 
    "statement_cache_size": 100
}

if settings.POSTGRES_SSL_REQUIRE:
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ssl_context

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=40,
    max_overflow=60,
    pool_timeout=30,
    pool_recycle=1800,
    echo=False,
    connect_args=connect_args
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session