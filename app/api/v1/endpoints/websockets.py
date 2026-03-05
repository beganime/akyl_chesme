from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError

from app.core.config import settings
from app.core.security import ALGORITHM
from app.schemas.token import TokenPayload
from app.db.session import get_db
from app.services.ws_manager import manager

router = APIRouter()

async def get_ws_current_user(token: str = Query(...)):
    """Зависимость для аутентификации пользователя по токену в URL"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)
        if token_data.sub is None:
            return None
        return token_data.sub # Возвращаем user_id
    except JWTError:
        return None

@router.websocket("/ws/chat")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str = Depends(get_ws_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 1. Защита соединения (Отказываем, если токен невалиден)
    if not user_id:
        await websocket.close(code=1008) # Policy Violation
        return

    # 2. Подключаем пользователя
    await manager.connect(websocket, user_id)

    try:
        while True:
            # 3. Ждем сообщений от мобильного приложения
            data = await websocket.receive_text()
            
            # Временно отправляем эхо-ответ для проверки (позже здесь будет сохранение в БД)
            response = {"status": "received", "your_text": data}
            await manager.send_personal_message(response, user_id)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)