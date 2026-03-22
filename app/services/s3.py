# app/services/s3.py
import pathlib
import uuid
import logging
from typing import Optional

import aioboto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {
    "jpg", "jpeg", "png", "webp", "gif",      # images
    "mp4", "mov", "avi", "mkv",               # video
    "mp3", "wav", "ogg", "m4a",               # audio
    "pdf", "doc", "docx", "txt",              # documents
}

CONTENT_TYPE_MAP = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "png": "image/png", "webp": "image/webp", "gif": "image/gif",
    "mp4": "video/mp4", "mov": "video/quicktime",
    "avi": "video/x-msvideo", "mkv": "video/x-matroska",
    "mp3": "audio/mpeg", "wav": "audio/wav",
    "ogg": "audio/ogg", "m4a": "audio/mp4",
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
}

# Публичный URL без presigned параметров (для аватаров)
PUBLIC_FOLDERS = {"avatars"}


class S3Service:
    def __init__(self):
        self.session = aioboto3.Session()
        self.bucket_name = settings.S3_BUCKET_NAME
        self.endpoint_url = settings.S3_ENDPOINT_URL
        # Конфиг с retry
        self._config = Config(
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=10,
            read_timeout=30,
        )

    def _client_kwargs(self) -> dict:
        return {
            "endpoint_url": self.endpoint_url,
            "aws_access_key_id": settings.S3_ACCESS_KEY,
            "aws_secret_access_key": settings.S3_SECRET_KEY,
            "config": self._config,
        }

    def _is_configured(self) -> bool:
        return bool(
            self.endpoint_url
            and settings.S3_ACCESS_KEY
            and settings.S3_SECRET_KEY
        )

    def _public_url(self, key: str) -> str:
        """Постоянный публичный URL для файлов в публичных папках."""
        base = self.endpoint_url.rstrip("/")
        return f"{base}/{self.bucket_name}/{key}"

    async def generate_presigned_url(
        self,
        filename: str,
        folder: str = "uploads",
        expires_in: int = 600,
    ) -> dict:
        if not self._is_configured():
            raise HTTPException(
                status_code=500,
                detail="S3 хранилище не настроено на сервере.",
            )

        suffix = pathlib.Path(filename).suffix.lower().lstrip(".")
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Недопустимое расширение файла: .{suffix}",
            )

        # Для аватаров используем имя как есть (user_id.ext)
        if folder in PUBLIC_FOLDERS:
            unique_key = f"{folder}/{filename}"
        else:
            unique_key = f"{folder}/{uuid.uuid4().hex}.{suffix}"

        content_type = CONTENT_TYPE_MAP.get(suffix, "application/octet-stream")

        try:
            async with self.session.client("s3", **self._client_kwargs()) as s3:
                upload_url = await s3.generate_presigned_url(
                    "put_object",
                    Params={
                        "Bucket": self.bucket_name,
                        "Key": unique_key,
                        "ContentType": content_type,
                    },
                    ExpiresIn=expires_in,
                )

            # Публичные папки — возвращаем постоянный URL
            if folder in PUBLIC_FOLDERS:
                file_url = self._public_url(unique_key)
            else:
                file_url = self._public_url(unique_key)

            return {
                "upload_url": upload_url,
                "file_url": file_url,
                "expires_in": expires_in,
                "content_type": content_type,
            }

        except ClientError as exc:
            logger.error("S3 presigned URL error: %s", exc)
            raise HTTPException(
                status_code=500,
                detail="Не удалось получить ссылку для загрузки файла.",
            ) from exc

    async def delete_file(self, file_url: str) -> bool:
        """Удалить файл из S3 по его URL."""
        if not self._is_configured():
            return False

        try:
            # Извлекаем key из URL
            base = f"{self.endpoint_url.rstrip('/')}/{self.bucket_name}/"
            if not file_url.startswith(base):
                return False
            key = file_url[len(base):]

            async with self.session.client("s3", **self._client_kwargs()) as s3:
                await s3.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception as e:
            logger.warning(f"S3 delete failed for {file_url}: {e}")
            return False


s3_service = S3Service()