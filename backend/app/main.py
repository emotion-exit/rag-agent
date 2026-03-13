import os
from typing import Any

import httpx
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import chat_router, knowledge_base_router

logger = logging.getLogger(__name__)

# Ensure data directories exist
os.makedirs(settings.chroma_persist_dir, exist_ok=True)
os.makedirs(settings.upload_dir, exist_ok=True)

app = FastAPI(
    title="RAG Agent API",
    description="Knowledge base Q&A agent powered by ADK, SiliconFlow, and OpenRouter",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(chat_router)
app.include_router(knowledge_base_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "detail": detail,
            "error_type": "http_error",
            "path": request.url.path,
        },
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    message = "请求参数校验失败"
    if errors:
        first_error = errors[0]
        location = " -> ".join(str(item) for item in first_error.get("loc", ()))
        error_message = str(first_error.get("msg", "参数不合法"))
        if location:
            message = f"请求参数校验失败：{location}，{error_message}"
        else:
            message = f"请求参数校验失败：{error_message}"

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "detail": message,
            "error_type": "validation_error",
            "path": request.url.path,
            "errors": errors,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "detail": f"服务器内部错误：{exc}",
            "error_type": exc.__class__.__name__,
            "path": request.url.path,
        },
    )


@app.get("/")
async def root():
    return {"message": "RAG Agent API is running", "docs": "/docs"}


@app.get("/health")
async def health():
    provider_states = _build_provider_status_summary()
    status = "ok"

    if any(item["status"] == "missing_config" for item in provider_states.values()):
        status = "degraded"

    return {
        "status": status,
        "providers": provider_states,
    }


def _build_provider_status_summary() -> dict[str, dict[str, Any]]:
    """返回轻量 provider 状态，不发起外网请求。"""
    return settings.get_provider_status_summary()


def _live_probe_provider(name: str, base_url: str, api_key: str, model: str, provider: str) -> dict[str, Any]:
    """对上游 provider 做一次轻量鉴权探测，区分缺配置与认证失败。"""
    normalized_key = api_key.strip()
    normalized_base_url = base_url.strip().rstrip("/")
    normalized_model = model.strip()
    normalized_provider = provider.strip()

    if not normalized_key:
        return {
            "status": "missing_config",
            "configured": False,
            "message": f"{name} 未配置 API Key",
            "base_url": normalized_base_url,
            "model": normalized_model,
            "provider": normalized_provider,
            "probe_mode": "http_get_models",
            "token_usage": "none_expected",
        }

    if not normalized_base_url:
        return {
            "status": "missing_config",
            "configured": False,
            "message": f"{name} 未配置 Base URL",
            "base_url": normalized_base_url,
            "model": normalized_model,
            "provider": normalized_provider,
            "probe_mode": "http_get_models",
            "token_usage": "none_expected",
        }

    try:
        response = httpx.get(
            f"{normalized_base_url}/models",
            headers={"Authorization": f"Bearer {normalized_key}"},
            timeout=8.0,
        )
    except httpx.TimeoutException:
        return {
            "status": "timeout",
            "configured": True,
            "message": f"{name} 健康检查超时",
            "base_url": normalized_base_url,
            "model": normalized_model,
            "provider": normalized_provider,
            "probe_mode": "http_get_models",
            "token_usage": "none_expected",
        }
    except httpx.HTTPError as exc:
        return {
            "status": "network_error",
            "configured": True,
            "message": f"{name} 健康检查失败：{exc}",
            "base_url": normalized_base_url,
            "model": normalized_model,
            "provider": normalized_provider,
            "probe_mode": "http_get_models",
            "token_usage": "none_expected",
        }

    if response.status_code in (401, 403):
        return {
            "status": "auth_error",
            "configured": True,
            "message": f"{name} 鉴权失败，请检查 API Key 是否有效",
            "base_url": normalized_base_url,
            "model": normalized_model,
            "provider": normalized_provider,
            "http_status": response.status_code,
            "probe_mode": "http_get_models",
            "token_usage": "none_expected",
        }

    if response.status_code >= 400:
        return {
            "status": "upstream_error",
            "configured": True,
            "message": f"{name} 上游返回异常状态码 {response.status_code}",
            "base_url": normalized_base_url,
            "model": normalized_model,
            "provider": normalized_provider,
            "http_status": response.status_code,
            "probe_mode": "http_get_models",
            "token_usage": "none_expected",
        }

    return {
        "status": "ok",
        "configured": True,
        "message": f"{name} 可用",
        "base_url": normalized_base_url,
        "model": normalized_model,
        "provider": normalized_provider,
        "http_status": response.status_code,
        "probe_mode": "http_get_models",
        "token_usage": "none_expected",
    }


@app.get("/health/providers")
async def health_providers():
    providers = {
        "embedding": _live_probe_provider(
            "Embedding",
            settings.embedding_base_url,
            settings.embedding_api_key,
            settings.embedding_model,
            settings.embedding_provider,
        ),
        "reranker": _live_probe_provider(
            "Reranker",
            settings.reranker_base_url,
            settings.reranker_api_key,
            settings.reranker_model,
            "siliconflow-rerank-http",
        ),
        "chat": _live_probe_provider(
            "Chat",
            settings.chat_base_url,
            settings.chat_api_key,
            settings.chat_model,
            "openai-compatible",
        ),
    }

    status = "ok"
    if any(item["status"] != "ok" for item in providers.values()):
        status = "degraded"

    return {
        "status": status,
        "providers": providers,
    }
