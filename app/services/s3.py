import uuid
import aioboto3
from botocore.exceptions import ClientError
from fastapi import UploadFile, HTTPException
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        # Используем aioboto3 для асинхронной работы с S3-совместимым API
        self.session = aioboto3.Session()
        self.bucket_name = settings.S3_BUCKET_NAME
        self.endpoint_url = settings.S3_ENDPOINT_URL

    async def upload_file(self, file: UploadFile, folder: str = "uploads") -> str:
        """
        Асинхронно загружает файл в S3 и возвращает публичный URL.
        Папка (folder) поможет структурировать файлы (например, 'avatars', 'chat_media').
        """
        if not self.endpoint_url or not settings.S3_ACCESS_KEY:
             raise HTTPException(status_code=500, detail="S3 storage is not configured.")

        # Генерируем уникальное имя файла, чтобы избежать коллизий
        file_extension = file.filename.split(".")[-1] if "." in file.filename else "bin"
        unique_filename = f"{folder}/{uuid.uuid4().hex}.{file_extension}"

        try:
            async with self.session.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY
            ) as s3_client:
                
                # Загружаем файл напрямую из потока (без сохранения на диск сервера)
                await s3_client.upload_fileobj(
                    file.file,
                    self.bucket_name,
                    unique_filename,
                    ExtraArgs={"ContentType": file.content_type}
                )
                
                # Формируем URL для доступа к файлу. 
                # Убедись, что бакет в Reg.ru настроен на публичное чтение.
                file_url = f"{self.endpoint_url}/{self.bucket_name}/{unique_filename}"
                return file_url

        except ClientError as e:
            logger.error(f"S3 Upload Error: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload file to storage")

# Инициализируем синглтон для использования в dependency injection
s3_service = S3Service()