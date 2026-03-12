import re
from collections import defaultdict
from typing import Any

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
QUERY_FILTER_FIELDS = ("system_name", "module_name", "feature_name", "version_name")
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
7. 不要输出多余的前言、中文分析过程、重复表述或与答案无关的自言自语。
8. 中文给出结论，如果给出结论，尽量直接给结论，再补充必要依据，不要先写长篇铺垫。
9. 不要向用户暴露任何内部实现细节，包括但不限于工具名、函数名、接口路径、类名、文件名、变量名、代码片段或“我调用了某个工具”这类描述。
10. 如果需要描述检索过程，只能用自然语言概括，例如“我已检索知识库并核对相关内容”，不要出现代码风格标识。
11. 不要输出你的思考过程、计划、推理步骤、自我提醒或工具调用痕迹。
12. 不要写“我现在需要”“接下来我会”“根据之前的工具调用”“让我分析一下”“我已经调用了”等第一人称过程描述。
13. 回答应直接从结论开始，除非知识库没有答案，否则不要复述用户问题，不要解释你如何得到答案。
14. 最终输出必须严格使用以下结构，不要添加结构外的内容：
<analysis_summary>
最多 3 条简短要点，概括候选依据或整理结果。
不要使用第一人称，不要写工具调用、检索过程、计划、自我思考。
</analysis_summary>
<final_answer>
直接填写最终答案本身，不要写说明文字，不要写“直接给用户的最终答案”这类模板句。
</final_answer>
15. 绝对不要照抄上面的结构说明文字，标签内部必须填写真实内容。
16. 如果已知答案，请直接在 <final_answer> 中填写真实结论，例如：
<analysis_summary>
- 文档中明确出现“初始密码为666”。
- 相关内容来自《宿舍管理.docx》的登录说明。
</analysis_summary>
<final_answer>
默认密码为 666（引自《宿舍管理.docx》）。
</final_answer>
17. 如果知识库中没有答案，也必须按相同结构输出，不要省略标签。"""


def _build_llm() -> LiteLlm:
    """Build LiteLLM model configured for OpenRouter."""
    return LiteLlm(
        model=f"openai/{settings.chat_model}",
        api_key=settings.openrouter_api_key,
        api_base=settings.openrouter_base_url,
        headers=settings.get_openrouter_headers(),
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


def _normalize_metadata_value(value: str) -> str:
    return re.sub(r"\s+", "", value.lower())


def _collect_filter_candidates() -> dict[str, set[str]]:
    candidates: dict[str, set[str]] = {field: set() for field in QUERY_FILTER_FIELDS}
    for document in vector_store.list_documents():
        for field in QUERY_FILTER_FIELDS:
            value = str(document.get(field, "")).strip()
            if value:
                candidates[field].add(value)
    return candidates


def _infer_metadata_filters(query: str) -> dict[str, str]:
    normalized_query = _normalize_metadata_value(query)
    if not normalized_query:
        return {}

    inferred: dict[str, str] = {}
    candidates = _collect_filter_candidates()

    for field, values in candidates.items():
        for value in sorted(values, key=len, reverse=True):
            if _normalize_metadata_value(value) in normalized_query:
                inferred[field] = value
                break

    return inferred


def _format_context_header(metadata: dict) -> str:
    header_parts = []
    for label, key in (
        ("系统", "system_name"),
        ("模块", "module_name"),
        ("功能", "feature_name"),
        ("版本", "version_name"),
        ("类型", "doc_type"),
    ):
        value = str(metadata.get(key, "")).strip()
        if value:
            header_parts.append(f"[{label}] {value}")

    source_type = str(metadata.get("source_type", "")).strip()
    if source_type:
        header_parts.append("[来源类型] 正文文本")

    source_label = str(metadata.get("source_label", "")).strip()
    if source_label:
        header_parts.append(f"[来源位置] {source_label}")

    heading_path = str(metadata.get("heading_path", "")).strip()
    if heading_path:
        header_parts.append(f"[章节路径] {heading_path}")

    section_title = str(metadata.get("section_title", "")).strip()
    if section_title and section_title != heading_path:
        header_parts.append(f"[章节标题] {section_title}")

    return "\n".join(header_parts)


def _metadata_match_count(query_terms: list[str], metadata: dict) -> int:
    values = [
        _normalize_text(str(metadata.get(field, "")))
        for field in QUERY_FILTER_FIELDS
    ]
    values.extend(
        [
            _normalize_text(str(metadata.get("section_title", ""))),
            _normalize_text(str(metadata.get("heading_path", ""))),
            _normalize_text(str(metadata.get("source_label", ""))),
        ]
    )
    return sum(1 for term in query_terms if any(term in value for value in values if value))


def _score_document(query_terms: list[str], doc: dict) -> tuple[float, int]:
    content = _normalize_text(doc.get("content", ""))
    distance = float(doc.get("distance", 1.0))
    semantic_score = max(0.0, 1.0 - distance)

    if not query_terms:
        return semantic_score, 0

    keyword_hits = sum(1 for term in query_terms if term in content)
    weighted_hits = sum(len(term) for term in query_terms if term in content)
    keyword_score = min(weighted_hits / max(len("".join(query_terms)), 1), 1.0)
    metadata_hits = _metadata_match_count(query_terms, doc.get("metadata", {}))
    metadata_score = min(metadata_hits / max(len(query_terms), 1), 1.0)
    final_score = semantic_score * 0.55 + keyword_score * 0.3 + metadata_score * 0.15
    return final_score, keyword_hits + metadata_hits


def _build_rerank_status(mode: str) -> str:
    if mode == RERANK_MODE_MODEL:
        return "已完成候选片段排序。"
    return "已完成候选片段排序。"


def build_retrieval_progress_steps(trace: dict[str, Any]) -> list[str]:
    steps: list[str] = []

    if trace.get("used_metadata_filters"):
        steps.append("已识别问题中的文档范围，正在限定检索范围。")
    else:
        steps.append("已完成问题理解，正在检索相关内容。")

    initial_hit_count = int(trace.get("initial_hit_count", 0) or 0)
    filtered_hit_count = int(trace.get("filtered_hit_count", 0) or 0)
    final_hit_count = int(trace.get("final_hit_count", 0) or 0)

    if initial_hit_count <= 0:
        steps.append("初步召回未找到相关片段。")
        steps.append("正在整理检索结果并生成说明。")
        return steps

    steps.append(f"已完成初步召回，找到 {initial_hit_count} 个候选片段。")

    if filtered_hit_count > 0:
        steps.append(f"已完成相关度过滤，保留 {filtered_hit_count} 个候选片段。")
    else:
        steps.append("候选片段相关度不足，未保留可用内容。")
        steps.append("正在整理检索结果并生成说明。")
        return steps

    if filtered_hit_count > 1:
        steps.append(_build_rerank_status(str(trace.get("rerank_mode", RERANK_MODE_LOCAL))))

    if final_hit_count > 0:
        steps.append(f"已选取 {final_hit_count} 个片段用于生成答案。")
    else:
        steps.append("未找到可直接作答的参考内容，正在整理说明。")

    return steps


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


def retrieve_relevant_documents_trace(
    query: str,
    initial_n_results: int = INITIAL_RETRIEVAL_LIMIT,
    final_n_results: int = FINAL_CONTEXT_LIMIT,
) -> dict[str, Any]:
    metadata_filters = _infer_metadata_filters(query)
    results = vector_store.query_documents(
        query,
        n_results=initial_n_results,
        metadata_filters=metadata_filters,
    )
    fallback_without_filters = False

    if not results and metadata_filters:
        fallback_without_filters = True
        results = vector_store.query_documents(query, n_results=initial_n_results)

    if not results:
        return {
            "documents": [],
            "rerank_mode": RERANK_MODE_LOCAL,
            "initial_hit_count": 0,
            "filtered_hit_count": 0,
            "final_hit_count": 0,
            "metadata_filters": metadata_filters,
            "used_metadata_filters": bool(metadata_filters),
            "fallback_without_filters": fallback_without_filters,
        }

    filtered = [result for result in results if result["distance"] < RETRIEVAL_THRESHOLD]
    if not filtered:
        return {
            "documents": [],
            "rerank_mode": RERANK_MODE_LOCAL,
            "initial_hit_count": len(results),
            "filtered_hit_count": 0,
            "final_hit_count": 0,
            "metadata_filters": metadata_filters,
            "used_metadata_filters": bool(metadata_filters),
            "fallback_without_filters": fallback_without_filters,
        }

    reranked, rerank_mode = _rerank_documents(query, filtered, limit=final_n_results)
    return {
        "documents": reranked,
        "rerank_mode": rerank_mode,
        "initial_hit_count": len(results),
        "filtered_hit_count": len(filtered),
        "final_hit_count": len(reranked),
        "metadata_filters": metadata_filters,
        "used_metadata_filters": bool(metadata_filters),
        "fallback_without_filters": fallback_without_filters,
    }


def retrieve_relevant_documents_with_mode(
    query: str,
    initial_n_results: int = INITIAL_RETRIEVAL_LIMIT,
    final_n_results: int = FINAL_CONTEXT_LIMIT,
) -> tuple[list[dict], str]:
    trace = retrieve_relevant_documents_trace(
        query,
        initial_n_results=initial_n_results,
        final_n_results=final_n_results,
    )
    return list(trace["documents"]), str(trace["rerank_mode"])


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
    trace = retrieve_relevant_documents_trace(
        query,
        initial_n_results=INITIAL_RETRIEVAL_LIMIT,
        final_n_results=n_results,
    )
    relevant = list(trace["documents"])
    rerank_mode = str(trace["rerank_mode"])
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
                "system_name": metadata.get("system_name", ""),
                "module_name": metadata.get("module_name", ""),
                "feature_name": metadata.get("feature_name", ""),
                "version_name": metadata.get("version_name", ""),
                "doc_type": metadata.get("doc_type", ""),
                "source_type": metadata.get("source_type", "text"),
                "source_label": metadata.get("source_label", "正文文本"),
                "source_page": metadata.get("source_page", 0),
                "section_title": metadata.get("section_title", ""),
                "heading_path": metadata.get("heading_path", ""),
                "image_count": int(metadata.get("image_count", 0) or 0),
                "summary": _summarize_excerpt(content),
            }
        )

    return summaries, rerank_mode


def build_source_payload_with_trace(
    query: str,
    n_results: int = FINAL_SOURCE_LIMIT,
) -> tuple[list[dict], dict[str, Any]]:
    trace = retrieve_relevant_documents_trace(
        query,
        initial_n_results=INITIAL_RETRIEVAL_LIMIT,
        final_n_results=n_results,
    )

    summaries = []
    for index, doc in enumerate(trace["documents"], 1):
        metadata = doc.get("metadata", {})
        content = doc.get("content", "")
        summaries.append(
            {
                "index": index,
                "doc_id": metadata.get("doc_id", ""),
                "filename": metadata.get("filename", "未知文档"),
                "chunk_index": metadata.get("chunk_index", 0),
                "system_name": metadata.get("system_name", ""),
                "module_name": metadata.get("module_name", ""),
                "feature_name": metadata.get("feature_name", ""),
                "version_name": metadata.get("version_name", ""),
                "doc_type": metadata.get("doc_type", ""),
                "source_type": metadata.get("source_type", "text"),
                "source_label": metadata.get("source_label", "正文文本"),
                "source_page": metadata.get("source_page", 0),
                "section_title": metadata.get("section_title", ""),
                "heading_path": metadata.get("heading_path", ""),
                "image_count": int(metadata.get("image_count", 0) or 0),
                "summary": _summarize_excerpt(content),
            }
        )

    return summaries, trace


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
        metadata = doc["metadata"]
        filename = metadata.get("filename", "未知文档")
        header = _format_context_header(metadata)
        if header:
            context_parts.append(f"[来源 {i}: {filename}]\n{header}\n[内容]\n{doc['content']}")
        else:
            context_parts.append(f"[来源 {i}: {filename}]\n[内容]\n{doc['content']}")

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
