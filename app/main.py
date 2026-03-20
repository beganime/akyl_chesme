# app/main.py
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.v1.router import api_router
from app.api.v1.endpoints.pages import router as pages_router
from app.db.session import engine
from app.core.firebase import init_firebase
from app.services.ws_manager import manager

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    limiter = Limiter(key_func=get_remote_address)
    RATE_LIMITING = True
except ImportError:
    limiter = None
    RATE_LIMITING = False

# Корень проекта
ROOT = Path(__file__).parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_firebase()
    await manager.setup_rabbitmq()
    yield
    if manager.rmq_connection:
        await manager.rmq_connection.close()
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

if RATE_LIMITING and limiter:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore

# ── CORS ──────────────────────────────────────────────────────
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(o) for o in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ── Статические файлы: /static/logo.png, /static/sl_logo.png ──
# Папка: <project_root>/static/
# Положи туда:
#   static/logo.png      ← иконка приложения (1:1, круглая)
#   static/sl_logo.png   ← баннер Students Life (16:9)
static_dir = ROOT / "static"
static_dir.mkdir(exist_ok=True)   # создаём папку если нет
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ── Публичные HTML-страницы и /download/android ──────────────
# Монтируются на корень — до api_router чтобы / не перекрывался
app.include_router(pages_router)

# ── REST API: /api/v1/... ──────────────────────────────────────
app.include_router(api_router, prefix=settings.API_V1_STR)

# ── Health ─────────────────────────────────────────────────────
@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok", "service": "akyl-chesme-backend"}