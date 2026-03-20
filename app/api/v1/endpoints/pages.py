"""
app/api/v1/endpoints/pages.py

Публичные страницы и загрузка APK:

  GET /              → Главная страница (landing)
  GET /privacy       → Политика конфиденциальности (Google Play / App Store)
  GET /terms         → Условия использования
  GET /download/android  → Скачать APK (akyl_chat.apk)

Статические файлы (/static/logo.png, /static/sl_logo.png) монтируются
в main.py через StaticFiles.
"""
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

router = APIRouter()

# Корень проекта — на 4 уровня вверх от этого файла
ROOT = Path(__file__).parent.parent.parent.parent.parent

# Папки
TEMPLATES_DIR = ROOT / "templates"
DOWNLOADS_DIR = ROOT / "downloads"   # сюда кладём akyl_chat.apk через scp

# Имя APK-файла (менять здесь если переименуешь)
APK_FILENAME = "akyl_chat.apk"


def _html(filename: str) -> str:
    """Читает HTML из папки templates."""
    path = TEMPLATES_DIR / filename
    if not path.exists():
        return f"<h1 style='font-family:sans-serif;padding:40px;color:#fff;background:#09090F;min-height:100vh'>404 — {filename} не найден</h1>"
    return path.read_text(encoding="utf-8")


# ── HTML страницы ─────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page():
    """Главная страница мессенджера."""
    return HTMLResponse(content=_html("index.html"))


@router.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
async def privacy_policy():
    """
    Политика конфиденциальности.
    Этот URL вставляется в Google Play Console и App Store Connect.

    ✅ https://akyl-cheshmesi.online/privacy
    """
    return HTMLResponse(content=_html("privacy.html"))


@router.get("/terms", response_class=HTMLResponse, include_in_schema=False)
async def terms():
    """Условия использования."""
    return HTMLResponse(content=_html("privacy.html"))


# ── Скачивание APK ────────────────────────────────────────────────────────────

@router.get("/download/android", include_in_schema=False)
async def download_android():
    """
    Скачать APK для Android.

    Файл должен лежать в: <project_root>/downloads/akyl_chat.apk
    Загрузить на сервер:   scp akyl_chat.apk user@server:/path/to/project/downloads/

    Браузер получит файл с именем "AkylChatInstaller.apk" (Content-Disposition).
    """
    apk_path = DOWNLOADS_DIR / APK_FILENAME

    if not apk_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"APK файл не найден на сервере. "
                f"Загрузите файл по пути: {apk_path}"
            ),
        )

    # Размер файла для отображения в браузере
    file_size = apk_path.stat().st_size
    size_mb = round(file_size / (1024 * 1024), 1)

    return FileResponse(
        path=str(apk_path),
        media_type="application/vnd.android.package-archive",
        filename="AkylChatInstaller.apk",   # имя файла при скачивании
        headers={
            "Content-Length": str(file_size),
            "X-App-Version": "latest",
            "X-File-Size-MB": str(size_mb),
            # Разрешаем кэширование браузером на 1 час
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.get("/download/android/info", include_in_schema=False)
async def download_android_info():
    """
    Информация о доступной версии APK (JSON).
    Клиент может использовать для проверки обновлений.
    """
    apk_path = DOWNLOADS_DIR / APK_FILENAME

    if not apk_path.exists():
        return {"available": False, "message": "APK не загружен на сервер"}

    stat = apk_path.stat()
    return {
        "available": True,
        "filename": APK_FILENAME,
        "size_bytes": stat.st_size,
        "size_mb": round(stat.st_size / (1024 * 1024), 1),
        "last_updated": stat.st_mtime,
        "download_url": "/download/android",
        "platform": "android",
    }