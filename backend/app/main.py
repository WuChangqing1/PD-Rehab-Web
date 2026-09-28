"""FastAPI application entry point.

Run in development:
    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import APIError, ErrorCode, error_body
from app.core.logging import get_logger, setup_logging
from app.db.init_db import ensure_bootstrap_admin, ensure_schema
from app.ml.bootstrap import load_all_models

logger = get_logger(__name__)

MEDICAL_DISCLAIMER = (
    "本系统用于科研、辅助评估及康复训练展示，不能替代专业医生诊断和标准临床量表。"
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    logger.info("starting %s (env=%s)", settings.app_name, settings.app_env)

    settings.ensure_directories()
    created = ensure_schema()
    if created:
        logger.info("schema initialised; run 'alembic upgrade head' for migrations")
    ensure_bootstrap_admin()

    # Models are loaded exactly once, here, and then reused for every request.
    load_all_models()

    logger.info("startup complete; docs at /docs")
    yield
    logger.info("shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description=(
        "帕金森病智能辅助识别、运动状态量化与数字康复训练平台。\n\n"
        f"**医疗声明：** {MEDICAL_DISCLAIMER}\n\n"
        "所有模型输出均来自真实模型；模型未配置时接口返回 "
        "`MODEL_NOT_CONFIGURED`，系统不会返回伪造结果。"
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------- error shape
@app.exception_handler(APIError)
async def _api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=exc.headers)


@app.exception_handler(StarletteHTTPException)
async def _http_error_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=exc.headers)
    code = {
        401: ErrorCode.NOT_AUTHENTICATED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        409: ErrorCode.CONFLICT,
        413: ErrorCode.FILE_TOO_LARGE,
        415: ErrorCode.UNSUPPORTED_MEDIA_TYPE,
        501: ErrorCode.NOT_IMPLEMENTED,
    }.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(code, str(exc.detail)),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def _validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_body(
            ErrorCode.VALIDATION_ERROR,
            "请求参数校验失败。",
            # errors() may contain non-serialisable objects; coerce to str.
            [
                {"loc": list(e.get("loc", [])), "msg": str(e.get("msg")), "type": e.get("type")}
                for e in exc.errors()
            ],
        ),
    )


@app.exception_handler(Exception)
async def _unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content=error_body(ErrorCode.INTERNAL_ERROR, "服务器内部错误。"),
    )


# --------------------------------------------------------------------- routes
app.include_router(api_router, prefix="/api")


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "app": settings.app_name,
        "version": "0.1.0",
        "api": "/api",
        "docs": "/docs",
        "disclaimer": MEDICAL_DISCLAIMER,
    }
