import os
import json
from typing import Any

import httpx
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import (
    _base_settings,
    reset_request_settings_overrides,
    set_request_settings_overrides,
    settings,
)
from app.routers import auth_router, chat_router, knowledge_base_router, notes_router
from app.services.auth import (
    extract_token_from_request,
    get_user_by_token,
    initialize_auth_db,
    is_admin,
    reset_current_user,
    set_current_user,
)
from app.services.knowledge_spaces import initialize_knowledge_space_db
from app.services.notes import initialize_notes_db
from app.services.public_config import (
    get_system_public_config,
    get_user_public_config,
    initialize_public_config_db,
)
from app.config import USER_EDITABLE_PUBLIC_FRONTEND_CONFIG_FIELDS

logger = logging.getLogger(__name__)

# Ensure data directories exist
os.makedirs(_base_settings.chroma_persist_dir, exist_ok=True)
os.makedirs(_base_settings.upload_dir, exist_ok=True)
initialize_auth_db()
initialize_knowledge_space_db()
initialize_notes_db()
initialize_public_config_db()

app = FastAPI(
    title="RAG Agent API",
    description="Knowledge base Q&A agent powered by ADK, SiliconFlow, and OpenRouter",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_base_settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(knowledge_base_router)
app.include_router(notes_router)


@app.middleware("http")
async def apply_public_frontend_config(request: Request, call_next):
    auth_token = extract_token_from_request(request)
    current_user = get_user_by_token(auth_token) if auth_token else None
    raw_config = request.headers.get("x-rag-public-config", "").strip()
    if not raw_config:
        raw_config = request.query_params.get("public_config", "").strip()

    parsed_config: dict[str, Any] | None = None
    if raw_config and is_admin(current_user):
        try:
            payload = json.loads(raw_config)
            if isinstance(payload, dict):
                parsed_config = payload
        except json.JSONDecodeError:
            parsed_config = None

    if parsed_config is None:
        if current_user is not None:
            parsed_config = get_user_public_config(
                str(current_user.get("user_id") or ""),
                allowed_fields=None
                if is_admin(current_user)
                else USER_EDITABLE_PUBLIC_FRONTEND_CONFIG_FIELDS,
            )
        else:
            parsed_config = get_system_public_config()

    token = set_request_settings_overrides(parsed_config)
    user_token = set_current_user(current_user)
    request.state.current_user = current_user
    try:
        response = await call_next(request)

        if isinstance(response, StreamingResponse):
            original_body_iterator = response.body_iterator

            async def wrapped_body_iterator():
                stream_token = set_request_settings_overrides(parsed_config)
                stream_user_token = set_current_user(current_user)
                try:
                    async for chunk in original_body_iterator:
                        yield chunk
                finally:
                    reset_current_user(stream_user_token)
                    reset_request_settings_overrides(stream_token)

            response.body_iterator = wrapped_body_iterator()
    finally:
        reset_current_user(user_token)
        reset_request_settings_overrides(token)

    return response


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


def _sanitize_provider_result(item: dict[str, Any]) -> dict[str, Any]:
    """移除不适合公开前端展示的 provider 细节。"""
    sanitized = {
        "status": item.get("status", "unknown"),
        "configured": bool(item.get("configured", False)),
        "provider": item.get("provider", ""),
    }

    for key in ("message", "probe_mode", "token_usage", "http_status"):
        value = item.get(key)
        if value not in (None, ""):
            sanitized[key] = value

    return sanitized


def _sanitize_provider_map(providers: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        name: _sanitize_provider_result(item)
        for name, item in providers.items()
    }


@app.get("/health/public")
async def public_health():
    provider_states = _sanitize_provider_map(_build_provider_status_summary())
    status = "ok"

    if any(item["status"] == "missing_config" for item in provider_states.values()):
        status = "degraded"

    return {
        "status": status,
        "providers": provider_states,
    }


def _build_probe_result(
    *,
    status: str,
    configured: bool,
    message: str,
    detail: str = "",
    base_url: str,
    model: str,
    provider: str,
    probe_mode: str,
    token_usage: str,
    http_status: int | None = None,
) -> dict[str, Any]:
    payload = {
        "status": status,
        "configured": configured,
        "message": message,
        "detail": detail,
        "base_url": base_url,
        "model": model,
        "provider": provider,
        "probe_mode": probe_mode,
        "token_usage": token_usage,
    }
    if http_status is not None:
        payload["http_status"] = http_status
    return payload


def _extract_response_detail(response: httpx.Response) -> str:
    """提取上游响应中的可读错误详情。"""
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        for key in ("detail", "message", "error", "msg"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:240]
        compact = json.dumps(payload, ensure_ascii=False)
        return compact[:240]

    text = response.text.strip()
    return text[:240] if text else ""


def _probe_request(
    *,
    name: str,
    method: str,
    url: str,
    headers: dict[str, str],
    base_url: str,
    model: str,
    provider: str,
    probe_mode: str,
    token_usage: str,
    json_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """发送一次健康检查请求，并统一转换成前端可展示的状态。"""
    try:
        response = httpx.request(
            method,
            url,
            headers=headers,
            json=json_payload,
            timeout=8.0,
        )
    except httpx.TimeoutException:
        return _build_probe_result(
            status="timeout",
            configured=True,
            message=f"{name} 健康检查超时",
            base_url=base_url,
            model=model,
            provider=provider,
            probe_mode=probe_mode,
            token_usage=token_usage,
        )
    except httpx.HTTPError as exc:
        return _build_probe_result(
            status="network_error",
            configured=True,
            message=f"{name} 健康检查失败：{exc}",
            base_url=base_url,
            model=model,
            provider=provider,
            probe_mode=probe_mode,
            token_usage=token_usage,
        )

    if response.status_code in (401, 403):
        return _build_probe_result(
            status="auth_error",
            configured=True,
            message=f"{name} 鉴权失败，请检查 API Key 是否有效",
            detail=_extract_response_detail(response),
            base_url=base_url,
            model=model,
            provider=provider,
            probe_mode=probe_mode,
            token_usage=token_usage,
            http_status=response.status_code,
        )

    if response.status_code >= 400:
        return _build_probe_result(
            status="upstream_error",
            configured=True,
            message=f"{name} 上游返回异常状态码 {response.status_code}",
            detail=_extract_response_detail(response),
            base_url=base_url,
            model=model,
            provider=provider,
            probe_mode=probe_mode,
            token_usage=token_usage,
            http_status=response.status_code,
        )

    return _build_probe_result(
        status="ok",
        configured=True,
        message=f"{name} 可用",
        base_url=base_url,
        model=model,
        provider=provider,
        probe_mode=probe_mode,
        token_usage=token_usage,
        http_status=response.status_code,
    )


def _live_probe_provider(name: str, base_url: str, api_key: str, model: str, provider: str) -> dict[str, Any]:
    """对上游 provider 做一次能力级探测，区分缺配置、鉴权失败和接口异常。"""
    normalized_key = api_key.strip()
    normalized_base_url = base_url.strip().rstrip("/")
    normalized_model = model.strip()
    normalized_provider = provider.strip()

    if not normalized_key:
        return _build_probe_result(
            status="missing_config",
            configured=False,
            message=f"{name} 未配置 API Key",
            base_url=normalized_base_url,
            model=normalized_model,
            provider=normalized_provider,
            probe_mode="missing_config",
            token_usage="none_expected",
        )

    if not normalized_base_url:
        return _build_probe_result(
            status="missing_config",
            configured=False,
            message=f"{name} 未配置 Base URL",
            base_url=normalized_base_url,
            model=normalized_model,
            provider=normalized_provider,
            probe_mode="missing_config",
            token_usage="none_expected",
        )

    headers = {
        "Authorization": f"Bearer {normalized_key}",
        "Content-Type": "application/json",
    }

    if name == "Embedding":
        return _probe_request(
            name=name,
            method="POST",
            url=f"{normalized_base_url}/embeddings",
            headers=headers,
            json_payload={
                "model": normalized_model,
                "input": ["健康检查"],
            },
            base_url=normalized_base_url,
            model=normalized_model,
            provider=normalized_provider,
            probe_mode="http_post_embeddings",
            token_usage="minimal_embedding_probe",
        )

    if name == "Reranker":
        return _probe_request(
            name=name,
            method="POST",
            url=f"{normalized_base_url}/rerank",
            headers=headers,
            json_payload={
                "model": normalized_model,
                "query": "健康检查",
                "documents": ["健康检查"],
                "top_n": 1,
                "return_documents": False,
            },
            base_url=normalized_base_url,
            model=normalized_model,
            provider=normalized_provider,
            probe_mode="http_post_rerank",
            token_usage="minimal_rerank_probe",
        )

    return _probe_request(
        name=name,
        method="GET",
        url=f"{normalized_base_url}/models",
        headers={"Authorization": f"Bearer {normalized_key}"},
        base_url=normalized_base_url,
        model=normalized_model,
        provider=normalized_provider,
        probe_mode="http_get_models",
        token_usage="none_expected",
    )


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


@app.get("/health/providers/public")
async def public_health_providers():
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
        "providers": _sanitize_provider_map(providers),
    }
