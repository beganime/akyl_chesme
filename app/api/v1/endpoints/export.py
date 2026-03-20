import csv
import io
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.user import User

router = APIRouter()

# Явный whitelist таблиц — только эти можно экспортировать
ALLOWED_TABLES = {"users", "messages", "chats", "chat_members", "device_sessions"}


async def check_admin_access(current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if current_user.username not in settings.ADMIN_USERNAMES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough privileges")
    return current_user


@router.get("/table/{table_name}")
async def export_table_data(
    table_name: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(check_admin_access),
):
    # 1. Whitelist проверка
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Export for table '{table_name}' is not allowed.",
        )

    # 2. Дополнительная защита от SQL injection — только строчные буквы и _
    # Это защита от unicode bypass и других хитростей
    if not re.fullmatch(r'[a-z_]+', table_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid table name format.",
        )

    # 3. Безопасный запрос — table_name уже проверен дважды
    # Используем SQLAlchemy text() только с проверенным именем таблицы
    safe_table = table_name  # Безопасно после двух проверок выше
    query = text(
        f"SELECT * FROM {safe_table} ORDER BY created_at ASC LIMIT :limit OFFSET :offset"  # noqa: S608
    )

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
        headers={
            "Content-Disposition": f"attachment; filename={safe_table}_export_{offset}.csv"
        },
    )