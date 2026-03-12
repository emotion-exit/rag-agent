import httpx

from app.config import settings


def rerank_documents(query: str, documents: list[str]) -> list[dict]:
    """Rerank candidate documents using the configured reranker endpoint."""
    if not query.strip() or not documents:
        return []

    response = httpx.post(
        f"{settings.reranker_base_url.rstrip('/')}/rerank",
        headers={
            "Authorization": f"Bearer {settings.reranker_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.reranker_model,
            "query": query,
            "documents": documents,
            "top_n": len(documents),
            "return_documents": False,
            "max_chunks_per_doc": 1,
        },
        timeout=20.0,
    )
    response.raise_for_status()

    payload = response.json()
    return payload.get("results", [])