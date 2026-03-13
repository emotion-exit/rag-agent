import httpx

from app.config import settings


def rerank_documents(query: str, documents: list[str]) -> list[dict]:
    """Rerank candidate documents using the configured reranker endpoint."""
    if not query.strip() or not documents:
        return []

    if not settings.reranker_api_key.strip():
        raise RuntimeError(
            "未配置重排 API Key。请在 backend/.env 或桌面配置中设置 RERANKER_API_KEY。"
        )

    request_url = f"{settings.reranker_base_url.rstrip('/')}/rerank"
    headers = {
        "Authorization": f"Bearer {settings.reranker_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.reranker_model,
        "query": query,
        "documents": documents,
        "top_n": len(documents),
        "return_documents": False,
        "max_chunks_per_doc": 1,
    }

    try:
        response = httpx.post(
            request_url,
            headers=headers,
            json=payload,
            timeout=settings.get_reranker_timeout(),
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise RuntimeError(
            "重排服务请求超时：连接到上游模型服务时超时，请检查当前网络、代理配置，"
            "或确认 RERANKER_BASE_URL 是否可达后重试。"
        ) from exc
    except httpx.NetworkError as exc:
        raise RuntimeError(
            "重排服务连接失败：无法连接到上游模型服务，请检查网络连通性、代理配置，"
            "以及 RERANKER_BASE_URL 是否正确。"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"重排服务返回异常状态码：{exc}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"重排服务请求失败：{exc}") from exc

    payload = response.json()
    results = payload.get("results", [])
    if not isinstance(results, list):
        raise RuntimeError("重排服务返回了无法识别的响应结构。")

    return results