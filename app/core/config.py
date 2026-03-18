from typing import Annotated, Any
from pydantic import AnyHttpUrl, BeforeValidator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Валидатор для CORS, адаптированный под Pydantic V2
def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, (list, str)):
        return v
    raise ValueError(v)

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Akyl Chesme"
    
    # Секретный ключ должен быть статичным и храниться в .env
    # Сгенерируй его один раз через `openssl rand -hex 32` и положи в .env
    SECRET_KEY: str 
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    SERVER_REGION: str = "LOCAL"
    
    # Настройки облачного кластера PostgreSQL
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 6432        # Порт Managed PgBouncer (от Reg.ru)
    POSTGRES_DIRECT_PORT: int = 5432 # Прямой порт для миграций Alembic
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_SSL_REQUIRE: bool = True 

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        """URL для самого приложения (пойдет через облачный PgBouncer)"""
        url = f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        if self.POSTGRES_SSL_REQUIRE:
            url += "?ssl=require"
        return url

    @computed_field
    @property
    def DIRECT_DATABASE_URL(self) -> str:
        """URL для Alembic (всегда напрямую в БД, минуя пулер)"""
        url = f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_DIRECT_PORT}/{self.POSTGRES_DB}"
        if self.POSTGRES_SSL_REQUIRE:
            url += "?ssl=require"
        return url

    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    @computed_field
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    CELERY_BROKER_URL: str | None = None

    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    S3_BUCKET_NAME: str = "akyl-chesme-media"
    
    BACKEND_CORS_ORIGINS: Annotated[list[str] | str, BeforeValidator(parse_cors)] = []
    FIREBASE_CREDENTIALS_PATH: str | None = None

    # Pydantic V2 конфигурация
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_ignore_empty=True, 
        extra="ignore"
    )

settings = Settings()