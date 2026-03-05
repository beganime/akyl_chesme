from fastapi import APIRouter

# Инициализируем роутер для модуля авторизации
router = APIRouter()

@router.post("/login/access-token")
async def login_access_token():
    """
    OAuth2 совместимый эндпоинт для получения токена.
    (Вскоре добавим сюда проверку логина/пароля и БД)
    """
    return {"message": "Здесь будет генерация JWT токена"}

@router.post("/test-token")
async def test_token():
    """
    Эндпоинт для проверки валидности токена.
    """
    return {"message": "Токен валиден (заглушка)"}