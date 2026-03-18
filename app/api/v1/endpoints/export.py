import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.db import AsyncSessionLocal # Исправленный импорт
from app.api.deps import get_db, get_current_user
from app.models.user import User

router = APIRouter()

ALLOWED_TABLES = {"users", "messages", "chats", "chat_members", "device_sessions"}

async def check_admin_access(current_user: User = Depends(get_current_user)):
    """
    Проверка на администратора.
    ПОКА ЧТО: Разрешаем экспорт только авторизованным пользователям.
    TODO: Добавить поле is_admin в модель User.
    """
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    # if not current_user.is_admin: raise HTTPException(status_code=403, detail="Not enough privileges")
    return current_user

@router.get("/table/{table_name}")
async def export_table_data(
    table_name: str,
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(check_admin_access) # АКТИВИРОВАНА ЗАЩИТА
):
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Export for table '{table_name}' is not allowed."
        )

    query = text(f"SELECT * FROM {table_name} ORDER BY created_at ASC LIMIT :limit OFFSET :offset")
    result = await db.execute(query, {"limit": limit, "offset": offset})
    rows = result.mappings().all()

    if not rows:
        raise HTTPException(status_code=404, detail="No data found")

    async def iter_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        headers = rows[0].keys()
        writer.writerow(headers)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for row in rows:
            writer.writerow(row.values())
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table_name}_export_{offset}.csv"}
    )