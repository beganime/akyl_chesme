from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from typing import List

from app.db.session import get_db
from app.models.user import User
from app.models.device import DeviceSession
from app.schemas.device import DeviceCreate, DeviceResponse
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/", response_model=DeviceResponse, status_code=status.HTTP_200_OK)
async def register_device(
    request: Request,
    device_in: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Регистрация или обновление устройства для Push-уведомлений.
    Мобильное приложение должно вызывать этот эндпоинт при запуске или смене FCM токена.
    """
    # Получаем IP адрес клиента из реквеста
    client_ip = request.client.host if request.client else None

    # Ищем, есть ли уже этот токен в базе (возможно, юзер перелогинился)
    stmt = select(DeviceSession).where(DeviceSession.push_token == device_in.push_token)
    result = await db.execute(stmt)
    existing_device = result.scalars().first()

    if existing_device:
        # Если устройство найдено, обновляем данные (например, юзер зашел с другого аккаунта на том же телефоне)
        existing_device.user_id = current_user.id
        existing_device.device_name = device_in.device_name
        existing_device.location = device_in.location
        existing_device.ip_address = client_ip
        existing_device.is_active = True
        
        await db.commit()
        await db.refresh(existing_device)
        return existing_device

    # Иначе создаем новую сессию устройства
    new_device = DeviceSession(
        user_id=current_user.id,
        device_name=device_in.device_name,
        push_token=device_in.push_token,
        location=device_in.location,
        ip_address=client_ip,
        is_active=True
    )
    
    db.add(new_device)
    await db.commit()
    await db.refresh(new_device)
    return new_device

@router.get("/", response_model=List[DeviceResponse])
async def get_my_devices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить список всех устройств текущего пользователя.
    Полезно для экрана "Активные сеансы" в настройках профиля.
    """
    stmt = (
        select(DeviceSession)
        .where(
            DeviceSession.user_id == current_user.id,
            DeviceSession.is_active == True
        )
        .order_by(desc(DeviceSession.updated_at))
    )
    result = await db.execute(stmt)
    devices = result.scalars().all()
    
    return devices