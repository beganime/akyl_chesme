import uuid
import aioboto3
from botocore.exceptions import ClientError
from fastapi import UploadFile, HTTPException
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        self.session = aioboto3.Session()
        self.bucket_name = settings.S3_BUCKET_NAME
        self.endpoint_url = settings.S3_ENDPOINT_URL

    async def generate_presigned_url(self, filename: str, folder: str = "uploads", expires_in: int = 3600) -> dict:
        """
        Генерирует временную ссылку (Presigned URL) для прямой загрузки файла с мобилки в S3.
        Разгружает наш сервер на 100% при передаче медиафайлов.
        """
        if not self.endpoint_url or not settings.S3_ACCESS_KEY:
             raise HTTPException(status_code=500, detail="S3 storage is not configured.")

        # Генерируем уникальное имя файла
        file_extension = filename.split(".")[-1] if "." in filename else "bin"
        unique_filename = f"{folder}/{uuid.uuid4().hex}.{file_extension}"

        try:
            async with self.session.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY
            ) as s3_client:
                
                # Генерируем URL для PUT-запроса (действует 1 час)
                upload_url = await s3_client.generate_presigned_url(
                    'put_object',
                    Params={'Bucket': self.bucket_name, 'Key': unique_filename},
                    ExpiresIn=expires_in
                )
                
                # Формируем итоговый публичный URL (после загрузки)
                file_url = f"{self.endpoint_url}/{self.bucket_name}/{unique_filename}"
                
                return {
                    "upload_url": upload_url,
                    "file_url": file_url
                }

        except ClientError as e:
            logger.error(f"S3 Presigned URL Error: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate presigned URL")

s3_service = S3Service()