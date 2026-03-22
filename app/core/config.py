# app/core/config.py
import secrets
from typing import Any, Annotated

from pydantic import BeforeValidator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    if isinstance(v, (list, str)):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AkylChat"
    # production | staging | development
    ENVIRONMENT: str = "development"

    SECRET_KEY: str = secrets.token_urlsafe(32)
    INTERNAL_API_KEY: str = secrets.token_urlsafe(32)
    CORE_API_KEY: str = secrets.token_urlsafe(32)

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 часа в продакшне
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    SERVER_REGION: str = "LOCAL"

    # PostgreSQL
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_SSL_REQUIRE: bool = False

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return (
            "postgresql+asyncpg://"
            f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def DIRECT_DATABASE_URL(self) -> str:
        return self.DATABASE_URL

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None

    @computed_field
    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # RabbitMQ / Celery
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    CELERY_BROKER_URL: str | None = None

    # S3
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    S3_BUCKET_NAME: str = "akylchat-media"

    # CORS — для продакшна указывай явно
    BACKEND_CORS_ORIGINS: Annotated[list[str] | str, BeforeValidator(parse_cors)] = []

    # Firebase
    FIREBASE_CREDENTIALS_PATH: str | None = None

    # Admins
    ADMIN_USERNAMES: Annotated[list[str] | str, BeforeValidator(parse_cors)] = []

    # Продакшн лимиты
    MAX_UPLOAD_SIZE_MB: int = 50        # максимальный размер файла
    MAX_MESSAGE_LENGTH: int = 4000      # максимальная длина сообщения
    MAX_CHAT_MEMBERS: int = 500         # максимум участников в группе

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )


settings = Settings()