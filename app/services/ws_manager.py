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
        # Локальные сокеты на текущем сервере (ТМ или РФ)
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Redis остается для проверки статуса "В сети / Был недавно"
        self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        
        # RabbitMQ переменные
        self.rmq_connection = None
        self.rmq_channel = None
        self.exchange = None
        self.queue = None

    async def setup_rabbitmq(self):
        """Вызывается при старте сервера в main.py -> lifespan"""
        try:
            self.rmq_connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            self.rmq_channel = await self.rmq_connection.channel()
            
            # Для Active-Active Exchange должен быть durable=True, чтобы выдерживать падения узлов
            self.exchange = await self.rmq_channel.declare_exchange(
                "chat_events", 
                aio_pika.ExchangeType.DIRECT,
                durable=True
            )
            
            # Создаем Эксклюзивную очередь ДЛЯ ЭТОГО СЕРВЕРА. 
            self.queue = await self.rmq_channel.declare_queue("", exclusive=True, auto_delete=True)
            
            # Начинаем слушать очередь
            await self.queue.consume(self._on_rmq_message)
            logger.info(f"[{settings.SERVER_REGION}] RabbitMQ подключен. Очередь слушает межсерверную шину.")
        except Exception as e:
            logger.error(f"[{settings.SERVER_REGION}] Ошибка подключения к RabbitMQ: {e}")

    async def _on_rmq_message(self, message: aio_pika.abc.AbstractIncomingMessage):
        """Обработчик входящих сообщений ИЗ ШИНЫ (от других серверов)"""
        async with message.process():
            try:
                # Маршрутный ключ у нас вида "user_{user_id}"
                user_id = message.routing_key.replace("user_", "")
                
                # Если этот юзер физически подключен к нашему инстансу
                if user_id in self.active_connections:
                    ws = self.active_connections[user_id]
                    payload_str = message.body.decode()
                    await ws.send_text(payload_str)
            except Exception as e:
                logger.error(f"Ошибка обработки RabbitMQ сообщения: {e}")

    async def connect(self, websocket: WebSocket, user_id: str):
        """Пользователь подключается к WebSocket"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        
        # --- СВЯЗЫВАЕМ С ШИНОЙ ---
        if self.queue and self.exchange:
            await self.queue.bind(self.exchange, routing_key=f"user_{user_id}")
        
        await self.redis.set(f"online_status:{user_id}", "online")
        logger.info(f"User {user_id} connected to node {settings.SERVER_REGION}.")

    def disconnect(self, websocket: WebSocket, user_id: str):
        """Пользователь отключается"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        
        # --- ОТВЯЗЫВАЕМ ОТ ШИНЫ ---
        if self.queue and self.exchange:
            asyncio.create_task(self.queue.unbind(self.exchange, routing_key=f"user_{user_id}"))
        
        asyncio.create_task(self.redis.delete(f"online_status:{user_id}"))
        logger.info(f"User {user_id} disconnected from node {settings.SERVER_REGION}.")

    async def send_personal_message(self, message: dict, user_id: str):
        """
        Отправить сообщение пользователю.
        Доставляется через RabbitMQ. Шина сама найдет, к какому серверу 
        подключен получатель.
        """
        if self.exchange:
            payload = json.dumps(message).encode()
            # Добавлена персистентность сообщений (delivery_mode=2)
            await self.exchange.publish(
                aio_pika.Message(
                    body=payload,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key=f"user_{user_id}"
            )

manager = ConnectionManager()