import os
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import chat_router, knowledge_base_router

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
    return {
        "embedding": {
            "status": "ok" if settings.embedding_api_key.strip() else "missing_config",
            "configured": bool(settings.embedding_api_key.strip()),
            "base_url": settings.embedding_base_url,
            "model": settings.embedding_model,
        },
        "reranker": {
            "status": "ok" if settings.reranker_api_key.strip() else "missing_config",
            "configured": bool(settings.reranker_api_key.strip()),
            "base_url": settings.reranker_base_url,
            "model": settings.reranker_model,
        },
        "chat": {
            "status": "ok" if settings.chat_api_key.strip() else "missing_config",
            "configured": bool(settings.chat_api_key.strip()),
            "base_url": settings.chat_base_url,
            "model": settings.chat_model,
        },
    }


def _live_probe_provider(name: str, base_url: str, api_key: str, model: str) -> dict[str, Any]:
    """对上游 provider 做一次轻量鉴权探测，区分缺配置与认证失败。"""
    normalized_key = api_key.strip()
    normalized_base_url = base_url.strip().rstrip("/")
    normalized_model = model.strip()

    if not normalized_key:
        return {
            "status": "missing_config",
            "configured": False,
            "message": f"{name} 未配置 API Key",
            "base_url": normalized_base_url,
            "model": normalized_model,
        }

    if not normalized_base_url:
        return {
            "status": "missing_config",
            "configured": False,
            "message": f"{name} 未配置 Base URL",
            "base_url": normalized_base_url,
            "model": normalized_model,
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
        }
    except httpx.HTTPError as exc:
        return {
            "status": "network_error",
            "configured": True,
            "message": f"{name} 健康检查失败：{exc}",
            "base_url": normalized_base_url,
            "model": normalized_model,
        }

    if response.status_code in (401, 403):
        return {
            "status": "auth_error",
            "configured": True,
            "message": f"{name} 鉴权失败，请检查 API Key 是否有效",
            "base_url": normalized_base_url,
            "model": normalized_model,
            "http_status": response.status_code,
        }

    if response.status_code >= 400:
        return {
            "status": "upstream_error",
            "configured": True,
            "message": f"{name} 上游返回异常状态码 {response.status_code}",
            "base_url": normalized_base_url,
            "model": normalized_model,
            "http_status": response.status_code,
        }

    return {
        "status": "ok",
        "configured": True,
        "message": f"{name} 可用",
        "base_url": normalized_base_url,
        "model": normalized_model,
        "http_status": response.status_code,
    }


@app.get("/health/providers")
async def health_providers():
    providers = {
        "embedding": _live_probe_provider(
            "Embedding",
            settings.embedding_base_url,
            settings.embedding_api_key,
            settings.embedding_model,
        ),
        "reranker": _live_probe_provider(
            "Reranker",
            settings.reranker_base_url,
            settings.reranker_api_key,
            settings.reranker_model,
        ),
        "chat": _live_probe_provider(
            "Chat",
            settings.chat_base_url,
            settings.chat_api_key,
            settings.chat_model,
        ),
    }

    status = "ok"
    if any(item["status"] != "ok" for item in providers.values()):
        status = "degraded"

    return {
        "status": status,
        "providers": providers,
    }
