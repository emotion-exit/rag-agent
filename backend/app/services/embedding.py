import openai
from app.config import settings


def get_embedding(text: str) -> list[float]:
    """Get text embedding using the configured embedding endpoint."""
    if not settings.embedding_api_key.strip():
        raise RuntimeError(
            "未配置嵌入 API Key。请在 backend/.env 或桌面配置中设置 EMBEDDING_API_KEY，"
            "旧版变量名 SILICONFLOW_API_KEY 也支持。"
        )

    client = openai.OpenAI(
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
    )
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=text,
    )
    return response.data[0].embedding
