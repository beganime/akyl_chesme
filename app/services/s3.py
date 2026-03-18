import pathlib
import uuid
import logging

import aioboto3
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif", "mp4", "mov", "mp3", "wav", "pdf"}


class S3Service:
    def __init__(self):
        self.session = aioboto3.Session()
        self.bucket_name = settings.S3_BUCKET_NAME
        self.endpoint_url = settings.S3_ENDPOINT_URL

    async def generate_presigned_url(
        self,
        filename: str,
        folder: str = "uploads",
        expires_in: int = 600,
    ) -> dict:
        if not self.endpoint_url or not settings.S3_ACCESS_KEY or not settings.S3_SECRET_KEY:
            raise HTTPException(status_code=500, detail="S3 storage is not configured.")

        suffix = pathlib.Path(filename).suffix.lower().lstrip(".")
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Unsupported file extension")

        unique_filename = f"{folder}/{uuid.uuid4().hex}.{suffix}"

        try:
            async with self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
            ) as s3_client:
                upload_url = await s3_client.generate_presigned_url(
                    "put_object",
                    Params={"Bucket": self.bucket_name, "Key": unique_filename},
                    ExpiresIn=expires_in,
                )
                file_url = f"{self.endpoint_url}/{self.bucket_name}/{unique_filename}"
                return {"upload_url": upload_url, "file_url": file_url, "expires_in": expires_in}
        except ClientError as exc:
            logger.error("S3 Presigned URL Error: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to generate presigned URL") from exc


s3_service = S3Service()
