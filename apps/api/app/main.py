from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.auth.router import router as auth_router
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.errors import AppError, ErrorCode, normalize_http_detail
from app.core.logging import configure_logging, get_logger, log_event
from app.core.middleware import REQUEST_ID_HEADER, RequestIdMiddleware
from app.datasets.router import router as datasets_router
from app.evaluations.router import router as evaluations_router
from app.experiments.router import router as experiments_router
from app.projects.router import router as projects_router
from app.regression.router import router as regression_router
from app.traces.router import router as traces_router

# Prefer Starlette's non-deprecated alias; fall back to literal 422 (avoid deprecated attr).
_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)

settings = get_settings()
logger = get_logger("evalsure.api")


def _cors_origins() -> list[str]:
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    return origins or ["http://localhost:3000"]


def _validate_startup_config() -> None:
    if len(settings.jwt_secret) < 16:
        raise RuntimeError("EVALSURE_JWT_SECRET must be at least 16 characters")
    if not settings.database_url.startswith("postgresql"):
        raise RuntimeError("DATABASE_URL must be a PostgreSQL URL")
    if not settings.database_url_sync.startswith("postgresql"):
        raise RuntimeError("DATABASE_URL_SYNC must be a PostgreSQL URL")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging(debug=settings.debug)
    _validate_startup_config()
    log_event(logger, "app_startup", environment=settings.environment)
    yield
    log_event(logger, "app_shutdown")


app = FastAPI(
    title=settings.app_name,
    description="LLM evaluation and regression-testing platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "Accept", REQUEST_ID_HEADER],
    expose_headers=[REQUEST_ID_HEADER],
)
app.add_middleware(RequestIdMiddleware)

app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(projects_router, prefix=settings.api_prefix)
app.include_router(datasets_router, prefix=settings.api_prefix)
app.include_router(evaluations_router, prefix=settings.api_prefix)
app.include_router(experiments_router, prefix=settings.api_prefix)
app.include_router(regression_router, prefix=settings.api_prefix)
app.include_router(traces_router, prefix=settings.api_prefix)


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.as_body())


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    code, message, details = normalize_http_detail(exc.detail, exc.status_code)
    body: dict = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    issues = []
    for err in exc.errors():
        clean = {k: v for k, v in err.items() if k != "ctx"}
        # ctx may contain non-JSON-serializable exception objects
        ctx = err.get("ctx")
        if isinstance(ctx, dict):
            clean_ctx = {}
            for key, value in ctx.items():
                clean_ctx[key] = str(value) if isinstance(value, BaseException) else value
            clean["ctx"] = clean_ctx
        issues.append(clean)
    return JSONResponse(
        status_code=_UNPROCESSABLE,
        content={
            "error": {
                "code": ErrorCode.VALIDATION_ERROR,
                "message": "Request validation failed",
                "details": {"issues": issues},
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    log_event(logger, "unhandled_exception", error_type=type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": ErrorCode.INTERNAL_ERROR,
                "message": "Internal server error",
            }
        },
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness — process is up. Does not probe PostgreSQL or external providers."""
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@app.get("/ready")
async def ready() -> JSONResponse:
    """Readiness — verifies database connectivity with a cheap SELECT 1."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return JSONResponse(
            status_code=200,
            content={"status": "ready", "database": "ok"},
        )
    except Exception:  # noqa: BLE001
        log_event(logger, "readiness_failed")
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "unavailable",
                "error": {
                    "code": ErrorCode.INTERNAL_ERROR,
                    "message": "Database unavailable",
                },
            },
        )
