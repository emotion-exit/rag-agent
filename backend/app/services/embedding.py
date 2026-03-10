import openai
from app.config import settings


def get_embedding(text: str) -> list[float]:
    """Get text embedding using SiliconFlow API."""
    client = openai.OpenAI(
        api_key=settings.siliconflow_api_key,
        base_url=settings.siliconflow_base_url,
    )
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=text,
    )
    return response.data[0].embedding
