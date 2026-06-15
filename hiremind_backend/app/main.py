from fastapi import FastAPI
import logging
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.core.config import get_settings
from app.core.database import Base, engine
from app.api.routes import auth, assessments, ai, code, proctoring, reports, attempts, websocket

# Import models so SQLAlchemy registers them
import app.models.user  # noqa: F401

settings = get_settings()
Path("media/proctor").mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SmartSkale HireMind AI",
    description="Enterprise AI Hiring & Assessment Platform — Backend API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory="media"), name="media")

# ── Create tables on startup (use Alembic in production) ─────────────────────
@app.on_event("startup")
def create_tables():
    # Only auto-create tables in development. In staging/production,
    # database schema changes must be applied via Alembic migrations.
    if settings.environment and settings.environment.lower() == "development":
        logger.warning(
            "Environment is 'development' — creating tables with SQLAlchemy `create_all`. "
            "In production use Alembic migrations instead."
        )
        Base.metadata.create_all(bind=engine)
    else:
        logger.info(
            "Skipping automatic table creation (environment=%s). "
            "Apply migrations using Alembic instead.",
            settings.environment,
        )


@app.on_event("startup")
def check_judge0_configuration():
    """Warn on startup if Judge0 is not configured or local Judge0 may be required."""
    url = settings.judge0_api_url or ""
    if not url:
        logger.warning(
            "JUDGE0_API_URL is not configured. Code execution will fail."
        )
        return

    # If using localhost endpoint, remind developer to run the local Judge0 docker
    if "localhost" in url or "127.0.0.1" in url:
        logger.warning(
            "JUDGE0_API_URL points to a local address (%s). "
            "Ensure the local Judge0 service is running: `docker compose -f docker-compose.judge0.yml up -d`.",
            url,
        )


# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(assessments.router)
app.include_router(ai.router)
app.include_router(code.router)
app.include_router(proctoring.router)
app.include_router(reports.router)
app.include_router(attempts.router)
app.include_router(websocket.router)


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "HireMind AI", "version": "1.0.0"}


@app.get("/", tags=["Health"])
def root():
    return {
        "service": "SmartSkale HireMind AI API",
        "docs": "/docs",
        "health": "/health",
    }
