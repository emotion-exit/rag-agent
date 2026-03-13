import httpx
import openai

from app.config import settings
from app.services.embedding_text_splitter import count_tokens, normalize_embedding_text, split_text_for_embedding


EMBEDDING_BATCH_SIZE = 16


def _create_embedding_client() -> openai.OpenAI:
    return openai.OpenAI(
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        timeout=settings.get_embedding_timeout(),
        max_retries=1,
    )


def _tokenizer_model() -> str:
    return settings.get_embedding_tokenizer_model()


def _tokenizer_encoding() -> str:
    return settings.embedding_tokenizer_encoding


def _count_embedding_tokens(text: str) -> int:
    return count_tokens(text, _tokenizer_model(), _tokenizer_encoding())


def _split_for_resilient_embedding(text: str) -> list[str]:
    return split_text_for_embedding(
        text,
        max_tokens=settings.embedding_max_input_tokens,
        target_tokens=settings.embedding_target_chunk_tokens,
        overlap_tokens=settings.embedding_chunk_overlap_tokens,
        tokenizer_model=_tokenizer_model(),
        tokenizer_encoding=_tokenizer_encoding(),
    )


def _aggregate_embeddings(embeddings: list[list[float]], weights: list[int]) -> list[float]:
    if not embeddings:
        raise RuntimeError("嵌入服务未返回任何向量结果。")

    dimension = len(embeddings[0])
    weighted = [0.0] * dimension
    total_weight = float(sum(max(weight, 1) for weight in weights))

    for embedding, weight in zip(embeddings, weights):
        for index, value in enumerate(embedding):
            weighted[index] += float(value) * max(weight, 1)

    return [value / total_weight for value in weighted]


def _request_embedding_batch(batch: list[str]) -> list[list[float]]:
    client = _create_embedding_client()
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=batch,
    )
    ordered_items = sorted(response.data, key=lambda item: item.index)
    return [item.embedding for item in ordered_items]


def _embed_resilient_text(text: str, *, force_split: bool = False) -> list[float]:
    normalized = normalize_embedding_text(text)
    if not normalized:
        raise RuntimeError("嵌入服务拒绝处理：存在空白文本块，无法生成向量。")

    token_count = _count_embedding_tokens(normalized)
    if not force_split and token_count <= settings.embedding_max_input_tokens:
        return _embed_safe_texts([normalized])[0]

    pieces = _split_for_resilient_embedding(normalized)
    if len(pieces) <= 1:
        raise RuntimeError(
            "嵌入服务拒绝处理：文档片段超过模型输入上限，且无法进一步安全切分。"
        )

    embeddings = _embed_safe_texts(pieces)
    weights = [_count_embedding_tokens(piece) for piece in pieces]
    return _aggregate_embeddings(embeddings, weights)


def _handle_413_batch(batch: list[str]) -> list[list[float]]:
    if len(batch) == 1:
        return [_embed_resilient_text(batch[0], force_split=True)]

    mid = max(1, len(batch) // 2)
    return _embed_safe_texts(batch[:mid]) + _embed_safe_texts(batch[mid:])


def _embed_safe_texts(texts: list[str]) -> list[list[float]]:
    embeddings: list[list[float]] = []

    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start : start + EMBEDDING_BATCH_SIZE]
        try:
            embeddings.extend(_request_embedding_batch(batch))
        except openai.APIStatusError as exc:
            if getattr(exc, "status_code", None) == 413:
                embeddings.extend(_handle_413_batch(batch))
                continue
            raise

    return embeddings


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Get embeddings in batches using the configured embedding endpoint."""
    if not settings.embedding_api_key.strip():
        raise RuntimeError(
            "未配置嵌入 API Key。请在 backend/.env 或桌面配置中设置 EMBEDDING_API_KEY，"
            "旧版变量名 SILICONFLOW_API_KEY 也支持。"
        )

    if not texts:
        return []

    normalized_texts = []
    for text in texts:
        normalized = normalize_embedding_text(text)
        if not normalized:
            raise RuntimeError("嵌入服务拒绝处理：存在空白文本块，无法生成向量。")
        normalized_texts.append(normalized)

    embeddings: list[list[float] | None] = [None] * len(normalized_texts)
    safe_indices: list[int] = []
    safe_texts: list[str] = []

    try:
        for index, text in enumerate(normalized_texts):
            if _count_embedding_tokens(text) <= settings.embedding_max_input_tokens:
                safe_indices.append(index)
                safe_texts.append(text)
                continue

            embeddings[index] = _embed_resilient_text(text, force_split=True)

        safe_embeddings = _embed_safe_texts(safe_texts)
        for index, embedding in zip(safe_indices, safe_embeddings):
            embeddings[index] = embedding
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
                "嵌入服务拒绝处理：文本片段超过模型输入上限，且自动切分后仍无法完成嵌入。"
                "请降低 EMBEDDING_TARGET_CHUNK_TOKENS 或更换支持更长输入的嵌入模型。"
            ) from exc
        raise RuntimeError(f"嵌入服务返回异常状态码：{exc}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"嵌入服务请求失败：{exc}") from exc

    return [embedding for embedding in embeddings if embedding is not None]


def get_embedding(text: str) -> list[float]:
    """Get text embedding using the configured embedding endpoint."""
    embeddings = get_embeddings([text])
    return embeddings[0]
