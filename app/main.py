import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import database
from app.config import settings
from app.database import get_db
from app.logging_config import setup_logging
from app.routers import comments, labels, projects, tasks, users

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting TaskFlow API (log level %s)", settings.log_level)
    if not database.check_database(database.engine):
        logger.critical("Database is unavailable: API started but cannot serve data")
    yield
    logger.info("TaskFlow API stopped")


# Таблицы здесь НЕ создаются (никакого create_all) — схема меняется только миграциями Alembic.
app = FastAPI(title="TaskFlow API", version="1.0.0", lifespan=lifespan)

app.include_router(users.router, prefix="/v1/users", tags=["users"])
app.include_router(projects.router, prefix="/v1/projects", tags=["projects"])
app.include_router(labels.router, prefix="/v1/labels", tags=["labels"])
app.include_router(tasks.router, prefix="/v1/tasks", tags=["tasks"])
app.include_router(comments.router, prefix="/v1/comments", tags=["comments"])


@app.middleware("http")
async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    started = time.perf_counter()
    logger.debug("Request started: %s %s", request.method, request.url.path)
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "%s %s -> %s (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.exception_handler(StarletteHTTPException)
async def log_http_exception(request: Request, exc: StarletteHTTPException) -> Response:
    if exc.status_code < 500:
        logger.warning(
            "%s %s -> %s: %s", request.method, request.url.path, exc.status_code, exc.detail
        )
    else:
        logger.error(
            "%s %s -> %s: %s", request.method, request.url.path, exc.status_code, exc.detail
        )
    return await http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def log_validation_error(request: Request, exc: RequestValidationError) -> Response:
    logger.warning(
        "%s %s -> 422: %d validation error(s)",
        request.method,
        request.url.path,
        len(exc.errors()),
    )
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(Exception)
async def log_unhandled_exception(request: Request, exc: Exception) -> Response:
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/health", tags=["health"])
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """Проверяет соединение с БД: 200 — всё хорошо, 503 — БД недоступна."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable"
        ) from exc
    return {"status": "ok", "database": "up"}
