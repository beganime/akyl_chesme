from fastapi import APIRouter
from app.api.v1.endpoints import auth, users # Пока заглушки, создадим их далее

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
# Далее добавим chats, messages, bots