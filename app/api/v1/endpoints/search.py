from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_
from typing import List

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserResponse
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/", response_model=List[UserResponse])
async def global_search(
    q: str = Query(..., min_length=1, description="Строка для поиска (username или имя)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Глобальный поиск пользователей и ботов по username или полному имени.
    """
    stmt = select(User).where(
        or_(
            User.username.ilike(f"%{q}%"),
            User.name.ilike(f"%{q}%")
        )
    ).limit(20) # Ограничиваем выдачу для скорости
    
    result = await db.execute(stmt)
    users = result.scalars().all()
    
    return users