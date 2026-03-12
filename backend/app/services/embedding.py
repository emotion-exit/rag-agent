import openai
from app.config import settings


def get_embedding(text: str) -> list[float]:
    """Get text embedding using the configured embedding endpoint."""
    client = openai.OpenAI(
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
    )
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=text,
    )
    return response.data[0].embedding
