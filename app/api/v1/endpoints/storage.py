from fastapi import APIRouter, Depends, Query
from app.services.s3 import s3_service
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/presigned-url")
async def get_presigned_url(
    filename: str = Query(..., description="Имя файла, например: photo.jpg"),
    current_user: User = Depends(get_current_user)
):
    """
    Получить временную ссылку для загрузки медиафайла (фото, видео, голос).
    Мобильное приложение делает PUT-запрос файла на `upload_url`, а в сокет отправляет `file_url`.
    """
    return await s3_service.generate_presigned_url(filename=filename)