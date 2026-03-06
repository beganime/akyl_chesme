from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, websockets, chats, storage, search # Добавили chats

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(websockets.router, tags=["websockets"])
api_router.include_router(storage.router, prefix="/storage", tags=["storage"])
api_router.include_router(chats.router, prefix="/chats", tags=["chats"])
api_router.include_router(search.router, prefix="/search", tags=["search"])