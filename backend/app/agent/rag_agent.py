import re
from collections import defaultdict

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from app.config import settings
from app.services import vector_store
from app.services.reranker import rerank_documents


RETRIEVAL_THRESHOLD = 0.7  # cosine distance threshold (lower = more similar)
INITIAL_RETRIEVAL_LIMIT = 10
FINAL_CONTEXT_LIMIT = 3
FINAL_SOURCE_LIMIT = 3
MAX_CHUNKS_PER_DOCUMENT = 2
SOURCE_SUMMARY_LENGTH = 140
QUERY_STOPWORDS = {
    "请问",
    "一下",
    "一下子",
    "这个",
    "那个",
    "什么",
    "多少",
    "怎么",
    "如何",
    "是否",
    "可以",
    "一下吗",
}
RERANK_MODE_MODEL = "model"
RERANK_MODE_LOCAL = "local-fallback"

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


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def _extract_query_terms(query: str) -> list[str]:
    normalized = _normalize_text(query)
    if not normalized:
        return []

    terms: list[str] = []
    for token in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", normalized):
        if token in QUERY_STOPWORDS or len(token) <= 1:
            continue
        terms.append(token)

        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            for size in range(2, min(len(token), 4) + 1):
                for start in range(0, len(token) - size + 1):
                    piece = token[start : start + size]
                    if piece not in QUERY_STOPWORDS:
                        terms.append(piece)

    seen: set[str] = set()
    deduped: list[str] = []
    for term in sorted(terms, key=len, reverse=True):
        if term not in seen:
            deduped.append(term)
            seen.add(term)
    return deduped


def _score_document(query_terms: list[str], doc: dict) -> tuple[float, int]:
    content = _normalize_text(doc.get("content", ""))
    distance = float(doc.get("distance", 1.0))
    semantic_score = max(0.0, 1.0 - distance)

    if not query_terms:
        return semantic_score, 0

    keyword_hits = sum(1 for term in query_terms if term in content)
    weighted_hits = sum(len(term) for term in query_terms if term in content)
    keyword_score = min(weighted_hits / max(len("".join(query_terms)), 1), 1.0)
    final_score = semantic_score * 0.65 + keyword_score * 0.35
    return final_score, keyword_hits


def _build_rerank_status(mode: str) -> str:
    if mode == RERANK_MODE_MODEL:
        return f"已完成候选片段重排，当前使用 {settings.reranker_model}。"
    return "重排模型暂不可用，已切换为本地轻量重排。"


def _fallback_rerank_documents(query: str, documents: list[dict]) -> list[dict]:
    query_terms = _extract_query_terms(query)
    scored_docs: list[dict] = []

    for doc in documents:
        rerank_score, keyword_hits = _score_document(query_terms, doc)
        scored_docs.append(
            {
                **doc,
                "rerank_score": rerank_score,
                "keyword_hits": keyword_hits,
            }
        )

    scored_docs.sort(
        key=lambda item: (
            item["keyword_hits"] > 0,
            item["rerank_score"],
            -float(item.get("distance", 1.0)),
        ),
        reverse=True,
    )

    if any(doc["keyword_hits"] > 0 for doc in scored_docs):
        prioritized = [doc for doc in scored_docs if doc["keyword_hits"] > 0]
        fallback = [doc for doc in scored_docs if doc["keyword_hits"] == 0]
        return prioritized + fallback

    return scored_docs


def _rerank_documents(query: str, documents: list[dict], limit: int) -> tuple[list[dict], str]:
    scored_docs: list[dict]
    rerank_mode = RERANK_MODE_MODEL

    try:
        rerank_results = rerank_documents(
            query,
            [doc.get("content", "") for doc in documents],
        )

        reranked_by_model: list[dict] = []
        for item in rerank_results:
            index = item.get("index")
            if not isinstance(index, int) or index < 0 or index >= len(documents):
                continue

            reranked_by_model.append(
                {
                    **documents[index],
                    "rerank_score": float(item.get("relevance_score", 0.0)),
                    "keyword_hits": 0,
                }
            )

        scored_docs = reranked_by_model or _fallback_rerank_documents(query, documents)
        if not reranked_by_model:
            rerank_mode = RERANK_MODE_LOCAL
    except Exception:
        scored_docs = _fallback_rerank_documents(query, documents)
        rerank_mode = RERANK_MODE_LOCAL

    per_document_count: dict[str, int] = defaultdict(int)
    reranked: list[dict] = []

    for doc in scored_docs:
        metadata = doc.get("metadata", {})
        doc_id = metadata.get("doc_id") or metadata.get("filename") or ""
        if per_document_count[doc_id] >= MAX_CHUNKS_PER_DOCUMENT:
            continue

        reranked.append(doc)
        per_document_count[doc_id] += 1
        if len(reranked) >= limit:
            break

    return reranked, rerank_mode


def retrieve_relevant_documents_with_mode(
    query: str,
    initial_n_results: int = INITIAL_RETRIEVAL_LIMIT,
    final_n_results: int = FINAL_CONTEXT_LIMIT,
) -> tuple[list[dict], str]:
    results = vector_store.query_documents(query, n_results=initial_n_results)

    if not results:
        return [], RERANK_MODE_LOCAL

    filtered = [result for result in results if result["distance"] < RETRIEVAL_THRESHOLD]
    if not filtered:
        return [], RERANK_MODE_LOCAL

    return _rerank_documents(query, filtered, limit=final_n_results)


def retrieve_relevant_documents(
    query: str,
    initial_n_results: int = INITIAL_RETRIEVAL_LIMIT,
    final_n_results: int = FINAL_CONTEXT_LIMIT,
) -> list[dict]:
    relevant, _ = retrieve_relevant_documents_with_mode(
        query,
        initial_n_results=initial_n_results,
        final_n_results=final_n_results,
    )
    return relevant


def build_source_payload(
    query: str,
    n_results: int = FINAL_SOURCE_LIMIT,
) -> tuple[list[dict], str]:
    relevant, rerank_mode = retrieve_relevant_documents_with_mode(
        query,
        initial_n_results=INITIAL_RETRIEVAL_LIMIT,
        final_n_results=n_results,
    )
    summaries = []

    for index, doc in enumerate(relevant, 1):
        metadata = doc.get("metadata", {})
        content = doc.get("content", "")
        summaries.append(
            {
                "index": index,
                "doc_id": metadata.get("doc_id", ""),
                "filename": metadata.get("filename", "未知文档"),
                "chunk_index": metadata.get("chunk_index", 0),
                "summary": _summarize_excerpt(content),
            }
        )

    return summaries, rerank_mode


def build_source_summaries(query: str, n_results: int = FINAL_SOURCE_LIMIT) -> list[dict]:
    summaries, _ = build_source_payload(query, n_results=n_results)
    return summaries


def retrieve_from_knowledge_base(query: str) -> str:
    """Retrieve relevant documents from the knowledge base.

    Args:
        query: The user's question to search for in the knowledge base.

    Returns:
        Relevant context from the knowledge base, or a message indicating no results.
    """
    if vector_store.collection_count() == 0:
        return "【知识库为空，尚未上传任何文档。】"

    relevant, _ = retrieve_relevant_documents_with_mode(
        query,
        initial_n_results=INITIAL_RETRIEVAL_LIMIT,
        final_n_results=FINAL_CONTEXT_LIMIT,
    )

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
