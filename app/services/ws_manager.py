import json
import asyncio
import logging
from typing import Dict
from fastapi import WebSocket
import redis.asyncio as aioredis # Асинхронный клиент Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Локальное хранилище сокетов для текущего воркера
        self.active_connections: Dict[str, WebSocket] = {}
        # Асинхронное подключение к Redis
        self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        self.pubsub = self.redis.pubsub()

    async def connect(self, websocket: WebSocket, user_id: str):
        """Подключение нового пользователя к WebSocket и подписка в Redis"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        
        # Подписываем воркер на персональный канал пользователя в Redis
        await self.pubsub.subscribe(f"user_{user_id}")
        logger.info(f"User {user_id} connected and subscribed to Redis.")
        
        # Запускаем фоновую задачу для прослушивания сообщений из Redis
        asyncio.create_task(self._listen_to_redis(user_id))

    def disconnect(self, websocket: WebSocket, user_id: str):
        """Отключение пользователя"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        logger.info(f"User {user_id} disconnected.")
        # В продакшене здесь также нужно обновлять статус "Был в сети" в БД

    async def _listen_to_redis(self, user_id: str):
        """Фоновый слушатель: ждет сообщений из Redis и кидает их в сокет"""
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"]
                    target_user_id = channel.replace("user_", "")
                    
                    # Если адресат подключен к этому конкретному воркеру — отправляем
                    if target_user_id in self.active_connections:
                        ws = self.active_connections[target_user_id]
                        await ws.send_text(message["data"])
        except Exception as e:
            logger.error(f"Redis listener error for user {user_id}: {e}")

    async def send_personal_message(self, message: dict, user_id: str):
        """
        Публикует сообщение в Redis. 
        Неважно, к какому воркеру подключен получатель, Redis доставит сообщение!
        """
        await self.redis.publish(f"user_{user_id}", json.dumps(message))

# Синглтон для использования в эндпоинтах
manager = ConnectionManager()