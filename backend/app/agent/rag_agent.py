"""RAG 检索与 Agent 构建。

这个模块是问答链路的核心：
1. 从用户问题里提取关键词和潜在元数据过滤条件。
2. 先向向量库召回，再做相关度过滤和 rerank。
3. 把最终上下文拼成工具返回结果，交给 ADK Agent 生成答案。
"""

import re
from collections import defaultdict
from typing import Any

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from app.config import settings
from app.services import vector_store
from app.services.reranker import rerank_documents


# 向量检索距离阈值。这里使用的是 distance，数值越小代表语义越接近。
RETRIEVAL_THRESHOLD = 0.7
INITIAL_RETRIEVAL_LIMIT = 10
FINAL_CONTEXT_LIMIT = 3
FINAL_SOURCE_LIMIT = 3
# 限制单文档最多贡献多少个 chunk，避免某一份文档完全垄断上下文窗口。
MAX_CHUNKS_PER_DOCUMENT = 2
SOURCE_SUMMARY_LENGTH = 140
# 这些字段既用于元数据过滤，也用于给检索结果补充上下文头信息。
QUERY_FILTER_FIELDS = ("system_name", "module_name", "feature_name", "version_name")
# 中文问题里常见但没有判别力的停用词，避免它们干扰关键词匹配和本地 rerank。
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

SYSTEM_INSTRUCTION = """你是一个中文知识库问答助手，只能基于知识库作答。

回答规则：
1. 只输出最终答案，不要输出分析、推理、解释、思考过程、提示词或自言自语。
2. 只用中文回答，除非用户明确要求其他语言。
3. 最终答案必须是可直接渲染的 Markdown 正文。
4. 如果是步骤、流程、办理方法、排查方法，使用有序列表（1. 2. 3.）。
5. 如果是结论、说明、条件、差异，使用短段落或无序列表（- ）。
6. 不要复述用户问题，不要写前言，不要写“好的”“下面是答案”“根据知识库”“我来回答”“我需要”“首先分析”等铺垫。
7. 不要输出任何标签或结构化标记，例如：<think>、<analysis>、<final_answer>、XML、JSON、代码块围栏。
8. 不要输出英文分析句、英文提示语、英文过程话。
9. 如果知识库没有答案，只能回答：当前知识库中没有找到相关资料，无法回答您的问题。
10. 如果答案来自具体文档，在正文末尾自然写出来源文档名称。

简洁规则：
1. 优先回答用户当前最直接的问题，不要扩展到用户没有问的分支方案。
2. 如果知识库里存在多种路径，只选择与用户当前问题最贴近的一种回答；除非用户明确要求比较、汇总、批量方案，否则不要同时输出多套流程。
3. 一般控制在 3 到 6 条步骤或 1 到 3 个短段落内。
4. 不要把同义步骤重复改写，不要把常识性提醒写成长篇说明。
5. 如果需要补充提醒，只保留一条最必要的提醒。

输出前自检：
- 是否只有最终答案
- 是否没有英文过程话
- 是否没有标签
- 是否没有多余分支
- 是否足够简短

示例 1：
默认密码为 **xxx**。

来源：宿舍管理.docx

示例 2：
1. 进入【床位管理】。
2. 选择需要调宿的学生当前床位。
3. 点击“换床”并确认。

来源：宿舍管理.docx

不要输出示例说明，只输出最终答案。"""


def _build_llm() -> LiteLlm:
    """构建对话模型实例。

    这里统一从 settings 取模型名、温度和 OpenRouter 请求头，
    这样网页端、桌面端和未来其他入口都共用同一套模型配置逻辑。
    """
    return LiteLlm(
        model=f"openai/{settings.chat_model}",
        api_key=settings.openrouter_api_key,
        api_base=settings.openrouter_base_url,
        temperature=settings.chat_temperature,
        headers=settings.get_openrouter_headers(),
    )


def _summarize_excerpt(content: str, max_length: int = SOURCE_SUMMARY_LENGTH) -> str:
    """生成来源摘要。

    前端来源卡片只需要一小段可读摘要，不需要把完整 chunk 全量下发。
    这里会先把空白折叠，再做截断。
    """
    normalized = " ".join(content.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[:max_length].rstrip()}..."


def _normalize_text(text: str) -> str:
    """归一化文本，便于做低成本关键词比较。"""
    return re.sub(r"\s+", "", text.lower())


def _extract_query_terms(query: str) -> list[str]:
    """从用户问题中提取检索关键词。

    策略分两层：
    - 先抽出英文 / 数字串或连续中文片段。
    - 对较长中文片段再切出 2 到 4 字子串，提高命中模块名、功能名、按钮名的概率。
    """
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
    """把元数据值归一化为适合包含判断的形式。"""
    return re.sub(r"\s+", "", value.lower())


def _collect_filter_candidates() -> dict[str, set[str]]:
    """从现有知识库文档中收集所有可用于过滤的元数据候选值。"""
    candidates: dict[str, set[str]] = {field: set() for field in QUERY_FILTER_FIELDS}
    for document in vector_store.list_documents():
        for field in QUERY_FILTER_FIELDS:
            value = str(document.get(field, "")).strip()
            if value:
                candidates[field].add(value)
    return candidates


def _infer_metadata_filters(query: str) -> dict[str, str]:
    """从问题文本里推断元数据过滤条件。

    例如问题里直接出现了系统名、模块名或版本名时，
    可以先缩小向量检索范围，减少噪声召回。
    """
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
    """把文档元数据整理成上下文头。

    这段头信息会和正文 chunk 一起送给模型，
    帮助模型理解内容来自哪个系统、模块、功能或章节。
    """
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
    """统计 query_terms 在元数据中的命中数。"""
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
    """为本地 fallback rerank 计算综合分数。

    综合考虑三部分：
    - 向量语义分 semantic_score
    - 正文关键词命中 keyword_score
    - 元数据命中 metadata_score
    """
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
    """生成给前端进度条使用的 rerank 状态文案。"""
    if mode == RERANK_MODE_MODEL:
        return "已完成候选片段排序。"
    return "已完成候选片段排序。"


def build_retrieval_progress_steps(trace: dict[str, Any]) -> list[str]:
    """根据检索 trace 生成用户可见的进度步骤。"""
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
    """当模型 rerank 不可用时，使用本地规则排序候选文档。"""
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
    """对过滤后的候选文档做 rerank，并限制最终保留条数。"""
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

    # 即使某篇文档相关度很高，也只允许少量 chunk 进入最终上下文，避免答案过度偏向单一来源。
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
    """执行完整检索流程，并返回可追踪的中间状态。

    这个 trace 会被聊天流式接口复用，用于展示“已召回多少条、过滤后还剩多少条”等进度信息。
    """
    metadata_filters = _infer_metadata_filters(query)
    results = vector_store.query_documents(
        query,
        n_results=initial_n_results,
        metadata_filters=metadata_filters,
    )
    fallback_without_filters = False

    # 如果基于元数据过滤没有召回结果，就自动回退到无过滤检索，避免误过滤导致完全答不出来。
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
    """返回最终可用文档，以及 rerank 采用的模式。"""
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
    """兼容型包装函数，只关心最终文档列表时使用。"""
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
    """把检索结果转成前端来源卡片需要的轻量结构。"""
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
    """同时返回来源摘要和完整 trace，供流式接口展示检索进度。"""
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
    """仅返回来源摘要列表的简化入口。"""
    summaries, _ = build_source_payload(query, n_results=n_results)
    return summaries


def retrieve_from_knowledge_base(query: str) -> str:
    """供 Agent 调用的知识库工具。

    它返回的不是结构化 JSON，而是一段适合直接放进提示词上下文的文本：
    每个来源都带有来源头和正文内容，便于模型在回答时引用具体文档。
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

    # 这里按“来源头 + 正文”的格式拼接上下文，既保留来源可解释性，也尽量减少提示词噪声。
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
    """创建 ADK RAG Agent。

    Agent 本身只做一件事：
    调用 retrieve_from_knowledge_base 拿上下文，再按照 SYSTEM_INSTRUCTION 输出最终答案。
    """
    return Agent(
        name="rag_agent",
        model=_build_llm(),
        description="Knowledge base Q&A agent that only answers based on uploaded documents.",
        instruction=SYSTEM_INSTRUCTION,
        tools=[retrieve_from_knowledge_base],
    )
