# app/main.py
import time
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api.v1.router import api_router
from app.api.v1.endpoints.pages import router as pages_router
from app.db.session import engine
from app.core.firebase import init_firebase
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting AkylChat backend [{settings.SERVER_REGION}]")
    init_firebase()
    await manager.setup_rabbitmq()
    yield
    logger.info("Shutting down...")
    if manager.rmq_connection:
        try:
            await manager.rmq_connection.close()
        except Exception:
            pass
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.1",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=f"{settings.API_V1_STR}/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# ── Rate Limiting ─────────────────────────────────────────────────────────────
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("Rate limiting enabled")
except ImportError:
    logger.warning("slowapi not installed, rate limiting disabled")

# ── Security Headers Middleware ───────────────────────────────────────────────
@app.middleware("http")
async def security_headers(request: Request, call_next):
    start_time = time.time()
    response: Response = await call_next(request)

    # Базовые security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Время обработки для мониторинга
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))

    return response

# ── CORS ──────────────────────────────────────────────────────────────────────
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(o) for o in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
        max_age=3600,
    )

# ── Static files ──────────────────────────────────────────────────────────────
static_dir = ROOT / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(pages_router)
app.include_router(api_router, prefix=settings.API_V1_STR)

# ── Health checks ─────────────────────────────────────────────────────────────
@app.get("/health", include_in_schema=False)
async def health():
    return {
        "status": "ok",
        "service": "akylchat-backend",
        "region": settings.SERVER_REGION,
        "version": "1.0.1",
    }


@app.get("/health/detailed", include_in_schema=False)
async def health_detailed():
    """Детальный healthcheck — для внутренней диагностики."""
    checks = {}

    # Redis
    try:
        from app.services.ws_manager import manager as ws_manager
        await ws_manager.redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # RabbitMQ
    checks["rabbitmq"] = "ok" if (
        manager.rmq_connection and not manager.rmq_connection.is_closed
    ) else "disconnected"

    # DB
    try:
        from app.db.session import engine as db_engine
        async with db_engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
        status_code=200 if all_ok else 207,
    )