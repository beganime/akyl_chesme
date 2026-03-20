# app/services/ws_manager.py
import json
import asyncio
import logging
from typing import Dict
from fastapi import WebSocket
import redis.asyncio as aioredis
import aio_pika

from app.core.config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # Локальные сокеты на текущем сервере
        self.active_connections: Dict[str, WebSocket] = {}

        # Redis для онлайн-статусов (быстрый кэш)
        self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

        # RabbitMQ для межсерверного обмена
        self.rmq_connection = None
        self.rmq_channel = None
        self.exchange = None
        self.queue = None

    async def setup_rabbitmq(self):
        """Вызывается при старте сервера."""
        try:
            self.rmq_connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            self.rmq_channel = await self.rmq_connection.channel()
            self.exchange = await self.rmq_channel.declare_exchange(
                "chat_events",
                aio_pika.ExchangeType.DIRECT,
                durable=True,
            )
            # Эксклюзивная очередь для этого инстанса
            self.queue = await self.rmq_channel.declare_queue("", exclusive=True, auto_delete=True)
            await self.queue.consume(self._on_rmq_message)
            logger.info(f"[{settings.SERVER_REGION}] RabbitMQ подключён.")
        except Exception as e:
            logger.error(f"[{settings.SERVER_REGION}] RabbitMQ ошибка: {e}")

    async def _on_rmq_message(self, message: aio_pika.abc.AbstractIncomingMessage):
        """Входящие сообщения от других серверов."""
        async with message.process():
            try:
                user_id = message.routing_key.replace("user_", "")
                if user_id in self.active_connections:
                    ws = self.active_connections[user_id]
                    await ws.send_text(message.body.decode())
            except Exception as e:
                logger.error(f"RabbitMQ message error: {e}")

    async def connect(self, websocket: WebSocket, user_id: str):
        """Пользователь подключился."""
        await websocket.accept()
        self.active_connections[user_id] = websocket

        # Привязываем к RabbitMQ очереди
        if self.queue and self.exchange:
            await self.queue.bind(self.exchange, routing_key=f"user_{user_id}")

        # Онлайн статус в Redis
        await self.redis.set(f"online_status:{user_id}", "online")
        logger.info(f"User {user_id} connected [{settings.SERVER_REGION}]")

    def disconnect(self, websocket: WebSocket, user_id: str):
        """Пользователь отключился."""
        if user_id in self.active_connections:
            del self.active_connections[user_id]

        if self.queue and self.exchange:
            asyncio.create_task(
                self.queue.unbind(self.exchange, routing_key=f"user_{user_id}")
            )

        # Убираем из Redis
        asyncio.create_task(self.redis.delete(f"online_status:{user_id}"))
        logger.info(f"User {user_id} disconnected [{settings.SERVER_REGION}]")

    async def send_personal_message(self, message: dict, user_id: str):
        """
        Отправить сообщение пользователю через RabbitMQ.
        RabbitMQ маршрутизирует на нужный сервер где подключён пользователь.
        """
        if self.exchange:
            await self.exchange.publish(
                aio_pika.Message(
                    body=json.dumps(message).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=f"user_{user_id}",
            )
        else:
            # Fallback: прямая отправка если RabbitMQ не настроен
            if user_id in self.active_connections:
                try:
                    await self.active_connections[user_id].send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Direct send error for {user_id}: {e}")

    async def is_online(self, user_id: str) -> bool:
        """Проверить онлайн статус через Redis."""
        return bool(await self.redis.get(f"online_status:{user_id}"))


manager = ConnectionManager()