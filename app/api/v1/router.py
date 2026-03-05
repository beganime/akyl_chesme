from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, websockets

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(websockets.router, tags=["websockets"])
# Далее добавим chats, messages, bots