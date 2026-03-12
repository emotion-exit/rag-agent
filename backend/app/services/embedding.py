import httpx
import openai
from app.config import settings


EMBEDDING_BATCH_SIZE = 16


def _create_embedding_client() -> openai.OpenAI:
    return openai.OpenAI(
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        timeout=settings.get_embedding_timeout(),
        max_retries=1,
    )


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Get embeddings in batches using the configured embedding endpoint."""
    if not settings.embedding_api_key.strip():
        raise RuntimeError(
            "未配置嵌入 API Key。请在 backend/.env 或桌面配置中设置 EMBEDDING_API_KEY，"
            "旧版变量名 SILICONFLOW_API_KEY 也支持。"
        )

    if not texts:
        return []

    client = _create_embedding_client()
    embeddings: list[list[float]] = []

    try:
        for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = texts[start : start + EMBEDDING_BATCH_SIZE]
            response = client.embeddings.create(
                model=settings.embedding_model,
                input=batch,
            )
            ordered_items = sorted(response.data, key=lambda item: item.index)
            embeddings.extend(item.embedding for item in ordered_items)
    except openai.APITimeoutError as exc:
        raise RuntimeError(
            "嵌入服务请求超时：连接到上游模型服务时超时，请检查当前网络、代理配置，"
            "或确认 EMBEDDING_BASE_URL 是否可达后重试。"
        ) from exc
    except openai.APIConnectionError as exc:
        raise RuntimeError(
            "嵌入服务连接失败：无法连接到上游模型服务，请检查网络连通性、代理配置，"
            "以及 EMBEDDING_BASE_URL 是否正确。"
        ) from exc
    except openai.APIStatusError as exc:
        if getattr(exc, "status_code", None) == 413:
            raise RuntimeError(
                "嵌入服务拒绝处理：文档分块仍然过长，已超过上游模型的单段输入限制。"
                "请缩小分块大小后重试。"
            ) from exc
        raise RuntimeError(f"嵌入服务返回异常状态码：{exc}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"嵌入服务请求失败：{exc}") from exc

    return embeddings


def get_embedding(text: str) -> list[float]:
    """Get text embedding using the configured embedding endpoint."""
    embeddings = get_embeddings([text])
    return embeddings[0]
