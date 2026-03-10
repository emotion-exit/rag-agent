from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from app.config import settings
from app.services import vector_store


RETRIEVAL_THRESHOLD = 0.7  # cosine distance threshold (lower = more similar)
SOURCE_SUMMARY_LENGTH = 140

SYSTEM_INSTRUCTION = """你是一个知识库问答助手。你的职责是：
1. 根据用户的问题，从提供的知识库上下文中查找答案。
2. 只基于知识库中的内容回答问题，不要自由发挥或凭空捏造答案。
3. 如果知识库中没有找到与问题相关的内容，请明确告知用户："当前知识库中没有找到相关资料，无法回答您的问题。"
4. 回答时请引用来源文档名称，让用户知道答案来自哪里。
5. 保持回答简洁、准确、有帮助。优先输出 2-4 个要点或最多 3 个短段落。
6. 最终给用户的答案请使用 Markdown 格式输出；合适时使用列表、加粗和引用。
7. 不要输出多余的前言、英文分析过程、重复表述或与答案无关的自言自语。
8. 如果给出结论，尽量直接给结论，再补充必要依据，不要先写长篇铺垫。"""


def _build_llm() -> LiteLlm:
    """Build LiteLLM model configured for OpenRouter."""
    return LiteLlm(
        model=f"openai/{settings.chat_model}",
        api_key=settings.openrouter_api_key,
        api_base=settings.openrouter_base_url,
    )


def _summarize_excerpt(content: str, max_length: int = SOURCE_SUMMARY_LENGTH) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[:max_length].rstrip()}..."


def retrieve_relevant_documents(query: str, n_results: int = 5) -> list[dict]:
    results = vector_store.query_documents(query, n_results=n_results)

    if not results:
        return []

    return [result for result in results if result["distance"] < RETRIEVAL_THRESHOLD]


def build_source_summaries(query: str, n_results: int = 5) -> list[dict]:
    relevant = retrieve_relevant_documents(query, n_results=n_results)
    summaries = []

    for index, doc in enumerate(relevant, 1):
        metadata = doc.get("metadata", {})
        summaries.append(
            {
                "index": index,
                "filename": metadata.get("filename", "未知文档"),
                "chunk_index": metadata.get("chunk_index", 0),
                "summary": _summarize_excerpt(doc.get("content", "")),
            }
        )

    return summaries


def retrieve_from_knowledge_base(query: str) -> str:
    """Retrieve relevant documents from the knowledge base.

    Args:
        query: The user's question to search for in the knowledge base.

    Returns:
        Relevant context from the knowledge base, or a message indicating no results.
    """
    relevant = retrieve_relevant_documents(query, n_results=5)

    if vector_store.collection_count() == 0:
        return "【知识库为空，尚未上传任何文档。】"

    if not relevant:
        return "【知识库中未找到与该问题相关的内容。】"

    context_parts = []
    for i, doc in enumerate(relevant, 1):
        filename = doc["metadata"].get("filename", "未知文档")
        context_parts.append(f"[来源 {i}: {filename}]\n{doc['content']}")

    return "\n\n---\n\n".join(context_parts)


def create_rag_agent() -> Agent:
    """Create the RAG agent with OpenRouter LLM."""
    return Agent(
        name="rag_agent",
        model=_build_llm(),
        description="Knowledge base Q&A agent that only answers based on uploaded documents.",
        instruction=SYSTEM_INSTRUCTION,
        tools=[retrieve_from_knowledge_base],
    )
