# app/api/v1/endpoints/export.py
import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.session import get_db
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter()

# Белый список таблиц для предотвращения SQL-инъекций
ALLOWED_TABLES = {"users", "messages", "chats", "chat_members", "device_sessions"}

async def check_admin_access(current_user: User = Depends(get_current_user)):
    """
    Заглушка для проверки прав администратора. 
    В реальном приложении здесь должна быть проверка роли из БД.
    Например: if not current_user.is_admin: raise HTTPException(...)
    """
    # TODO: Добавить колонку is_admin в модель User в следующей миграции
    pass

@router.get("/table/{table_name}")
async def export_table_data(
    table_name: str,
    limit: int = Query(100, description="Количество строк за один чанк", le=1000),
    offset: int = Query(0, description="Смещение (с какой строки начать)"),
    db: AsyncSession = Depends(get_db),
    # Раскомментируйте ниже, чтобы включить защиту
    # _: None = Depends(check_admin_access)
):
    """
    Потоковая выгрузка данных из БД.
    Оптимизировано для выгрузки чанками, чтобы не перегружать RAM сервера "Акыл Чешме".
    """
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Export for table '{table_name}' is not allowed or table does not exist."
        )

    # Используем сырой SQL с параметрами (безопасно, т.к. имя таблицы валидировано выше)
    query = text(f"SELECT * FROM {table_name} ORDER BY created_at ASC LIMIT :limit OFFSET :offset")
    
    result = await db.execute(query, {"limit": limit, "offset": offset})
    rows = result.mappings().all()

    if not rows:
        raise HTTPException(status_code=404, detail="No data found or offset is too large")

    # Функция-генератор для стриминга CSV
    async def iter_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Пишем заголовки (названия колонок)
        headers = rows[0].keys()
        writer.writerow(headers)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        # Пишем данные
        for row in rows:
            writer.writerow(row.values())
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    filename = f"{table_name}_export_offset_{offset}.csv"
    
    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )