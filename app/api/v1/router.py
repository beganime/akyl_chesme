from fastapi import APIRouter
from app.api.v1.endpoints import auth, bot, devices, export, internal_bots, users, websockets, chats, storage, search # Добавили chats

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(websockets.router, tags=["websockets"])
api_router.include_router(storage.router, prefix="/storage", tags=["storage"])
api_router.include_router(chats.router, prefix="/chats", tags=["chats"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(bot.router, prefix="/bot", tags=["bot"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(internal_bots.router, prefix="/internal/bots", tags=["internal"])