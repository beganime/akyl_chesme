import secrets
from typing import Any, Union, List
from pydantic import AnyHttpUrl, BeforeValidator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Annotated

def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, (list, str)):
        return v
    raise ValueError(v)

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Akyl Chesme"
    
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    SERVER_REGION: str = "LOCAL"
    
    # === НОВОЕ: Ключ для внутреннего моста между микросервисами ===
    INTERNAL_API_KEY: str = "akyl_super_secret_internal_bridge_key_123!"
    
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    
    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @computed_field
    @property
    def DIRECT_DATABASE_URL(self) -> str:
        host = "db" if self.POSTGRES_SERVER == "pgbouncer" else self.POSTGRES_SERVER
        port = 5432 if self.POSTGRES_SERVER == "pgbouncer" else self.POSTGRES_PORT
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{host}:{port}/{self.POSTGRES_DB}"

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

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_ignore_empty=True, 
        extra="ignore"
    )

settings = Settings()