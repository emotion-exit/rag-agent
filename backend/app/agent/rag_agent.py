"""RAG 检索与 Agent 构建。

这个模块是问答链路的核心：
1. 从用户问题里提取关键词和潜在元数据过滤条件。
2. 先向向量库召回，再做相关度过滤和 rerank。
3. 把最终上下文拼成工具返回结果，交给 ADK Agent 生成答案。
"""

import copy
import json
import re
from collections import defaultdict
from typing import Any

import openai
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from app.config import settings
from app.services import vector_store
from app.services.reranker import rerank_documents


# 向量检索距离阈值。这里使用的是 distance，数值越小代表语义越接近。
RETRIEVAL_THRESHOLD = 0.7
INITIAL_RETRIEVAL_LIMIT = max(int(settings.retrieval_candidate_limit), 1)
FINAL_CONTEXT_LIMIT = max(int(settings.retrieval_final_context_limit), 1)
FINAL_SOURCE_LIMIT = max(int(settings.retrieval_source_limit), 1)
QUERY_EXPANSION_LIMIT = max(int(settings.retrieval_query_expansion_count), 0)
# 限制单文档最多贡献多少个 chunk，避免某一份文档完全垄断上下文窗口。
MAX_CHUNKS_PER_DOCUMENT = 2
SOURCE_SUMMARY_LENGTH = 140
HITL_OPTION_LIMIT = 4
HITL_DISTANCE_THRESHOLD = 0.42
EVIDENCE_STRONG_DISTANCE_THRESHOLD = 0.38
EVIDENCE_MAX_DISTANCE_THRESHOLD = 0.55
EVIDENCE_MIN_COVERAGE = 0.5
# 这些字段既用于元数据过滤，也用于给检索结果补充上下文头信息。
QUERY_FILTER_FIELDS = ("knowledge_space", "category", "topic", "version_label")
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
ALLOWED_METADATA_FILTER_FIELDS = ("knowledge_space", "category", "topic", "version_label")
NO_KNOWLEDGE_BASE_ANSWER = "当前知识库中没有找到相关资料，无法回答您的问题。"
KNOWLEDGE_SPACE_RESOLUTION_PROBE_LIMIT = max(INITIAL_RETRIEVAL_LIMIT, 8)
KNOWLEDGE_SPACE_RESOLVED = "resolved"
KNOWLEDGE_SPACE_AMBIGUOUS = "ambiguous"
KNOWLEDGE_SPACE_UNKNOWN = "unknown"
SESSION_CACHE_MAX_SESSIONS = 64
SESSION_CACHE_MAX_ENTRIES_PER_BUCKET = 128

_SESSION_RETRIEVAL_CACHE: dict[str, dict[str, dict[str, Any]]] = {}

CORE_SYSTEM_INSTRUCTION = """核心指令（必须严格遵守）

你是一个中文知识库问答助手，只能基于知识库作答。

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

不要输出示例说明，只输出最终答案。"""

ADVISORY_SYSTEM_GUIDANCE = """优化建议（在不违背核心指令时优先参考）

1. 优先吸收来源中的章节标题、版本、标签和知识空间信息，用它们来约束答案范围。
2. 当问题偏口语化时，把它映射为知识库里更正式的表达后再组织答案，但不要把改写过程写出来。
3. 多个来源存在轻微差异时，优先采用更贴近用户当前知识空间、版本和主题的来源。
4. 如果答案需要引用来源，把来源文档名自然放在正文末尾，不要堆砌检索细节。
5. 如果用户的问题非常宽泛，只回答当前问题最关键的部分，避免无关扩写。"""

SYSTEM_INSTRUCTION = f"{CORE_SYSTEM_INSTRUCTION}\n\n{ADVISORY_SYSTEM_GUIDANCE}"


def _build_llm() -> LiteLlm:
    """构建对话模型实例。

    这里统一从 settings 取模型名、温度和 OpenRouter 请求头，
    这样网页端、桌面端和未来其他入口都共用同一套模型配置逻辑。
    """
    return LiteLlm(
        model=f"openai/{settings.chat_model}",
        api_key=settings.chat_api_key,
        api_base=settings.chat_base_url,
        temperature=settings.chat_temperature,
        headers=settings.get_chat_headers(),
    )


def _build_auxiliary_client() -> openai.OpenAI:
    """构建用于检索增强的小型对话客户端。"""
    return openai.OpenAI(
        api_key=settings.chat_api_key,
        base_url=settings.chat_base_url,
        default_headers=settings.get_chat_headers(),
        timeout=20.0,
        max_retries=1,
    )


def _run_auxiliary_completion(system_prompt: str, user_prompt: str) -> str:
    """调用同一套聊天模型做检索辅助任务。"""
    if not settings.chat_api_key.strip() or not settings.chat_model.strip() or not settings.chat_base_url.strip():
        return ""

    try:
        client = _build_auxiliary_client()
        response = client.chat.completions.create(
            model=settings.chat_model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception:
        return ""

    message = response.choices[0].message if response.choices else None
    return str(getattr(message, "content", "") or "").strip()


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


def _extract_core_query_terms(query: str) -> list[str]:
    """提取用于证据充分性判断的核心词，不再展开中文子串。"""
    normalized = _normalize_text(query)
    if not normalized:
        return []

    terms: list[str] = []
    for token in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", normalized):
        if token in QUERY_STOPWORDS:
            continue
        if re.fullmatch(r"[a-z0-9]+", token):
            if len(token) >= 2:
                terms.append(token)
            continue

        if len(token) >= 2:
            terms.append(token)

    seen: set[str] = set()
    deduped: list[str] = []
    for term in sorted(terms, key=len, reverse=True):
        if term not in seen:
            deduped.append(term)
            seen.add(term)
    return deduped


def _extract_explicit_identifier_terms(query: str) -> list[str]:
    """提取问题中的显式标识词。

    这类词通常是人名、产品名、语言名、型号、缩写、编号等，
    一旦问题里明确写出，证据中至少应出现一次，否则说明答非所问风险很高。
    """
    normalized = _normalize_text(query)
    if not normalized:
        return []

    identifiers = [
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_+#\.-]*", normalized)
        if len(token) >= 2
    ]

    seen: set[str] = set()
    deduped: list[str] = []
    for term in sorted(identifiers, key=len, reverse=True):
        if term not in seen:
            deduped.append(term)
            seen.add(term)
    return deduped


def _normalize_metadata_value(value: str) -> str:
    """把元数据值归一化为适合包含判断的形式。"""
    return re.sub(r"\s+", "", value.lower())


def _extract_json_object(raw_text: str) -> dict[str, Any] | None:
    """从模型文本中提取第一个 JSON 对象。"""
    text = str(raw_text or "").strip()
    if not text:
        return None

    candidates = [text]
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidates.insert(0, match.group(0))

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload

    return None


def _build_cache_key(query: str, suffix: str = "") -> str:
    """构建会话内缓存键。"""
    normalized_query = _normalize_text(query)
    return f"{normalized_query}::{suffix}" if suffix else normalized_query


def _get_session_cache_bucket(session_id: str | None, bucket_name: str) -> dict[str, Any] | None:
    """获取指定会话的某个缓存桶。"""
    if not session_id:
        return None

    session_cache = _SESSION_RETRIEVAL_CACHE.setdefault(session_id, {})
    bucket = session_cache.setdefault(bucket_name, {})

    while len(_SESSION_RETRIEVAL_CACHE) > SESSION_CACHE_MAX_SESSIONS:
        oldest_session_id = next(iter(_SESSION_RETRIEVAL_CACHE))
        if oldest_session_id == session_id and len(_SESSION_RETRIEVAL_CACHE) == 1:
            break
        _SESSION_RETRIEVAL_CACHE.pop(oldest_session_id, None)

    return bucket


def _read_session_cache(session_id: str | None, bucket_name: str, cache_key: str) -> Any | None:
    """读取会话内缓存项。"""
    bucket = _get_session_cache_bucket(session_id, bucket_name)
    if bucket is None:
        return None
    return bucket.get(cache_key)


def _write_session_cache(session_id: str | None, bucket_name: str, cache_key: str, value: Any) -> None:
    """写入会话内缓存项，并控制单桶大小。"""
    bucket = _get_session_cache_bucket(session_id, bucket_name)
    if bucket is None:
        return

    if cache_key in bucket:
        bucket.pop(cache_key, None)
    bucket[cache_key] = value

    while len(bucket) > SESSION_CACHE_MAX_ENTRIES_PER_BUCKET:
        oldest_key = next(iter(bucket))
        bucket.pop(oldest_key, None)


def _normalize_explicit_metadata_filters(
    metadata_filters: dict[str, str] | None,
) -> dict[str, str]:
    """清洗前端传入的显式过滤条件，只保留受支持字段。"""
    if not metadata_filters:
        return {}

    normalized_filters: dict[str, str] = {}
    for field in ALLOWED_METADATA_FILTER_FIELDS:
        value = str(metadata_filters.get(field, "") or "").strip()
        if value:
            normalized_filters[field] = value

    return normalized_filters


def _merge_metadata_filters(
    inferred_filters: dict[str, str],
    explicit_filters: dict[str, str] | None,
) -> dict[str, str]:
    """合并推断过滤与显式过滤，显式过滤优先。"""
    merged = dict(inferred_filters)
    merged.update(_normalize_explicit_metadata_filters(explicit_filters))
    return merged


def _collect_filter_candidates() -> dict[str, set[str]]:
    """从现有知识库文档中收集所有可用于过滤的元数据候选值。"""
    candidates: dict[str, set[str]] = {field: set() for field in QUERY_FILTER_FIELDS}
    for document in vector_store.list_documents():
        for field in QUERY_FILTER_FIELDS:
            value = str(document.get(field, "")).strip()
            if value:
                candidates[field].add(value)
    return candidates


def _collect_knowledge_spaces() -> list[str]:
    """返回当前知识库里所有知识空间。"""
    spaces = {
        str(document.get("knowledge_space", "") or "").strip()
        for document in vector_store.list_documents()
    }
    return sorted(space for space in spaces if space)


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


def _rank_knowledge_space_candidates(query: str, candidates: list[str]) -> list[str]:
    """按问题文本对候选知识空间做轻量排序。"""
    query_terms = _extract_core_query_terms(query)

    def score(space: str) -> tuple[int, int, str]:
        normalized_space = _normalize_text(space)
        hit_count = sum(
            1
            for term in query_terms
            if term in normalized_space or normalized_space in term
        )
        return (-hit_count, -len(space), space)

    return sorted(candidates, key=score)


def _probe_knowledge_space_candidates(query: str) -> list[str]:
    """通过一次宽松召回给知识空间澄清提供候选。"""
    try:
        probe_results = vector_store.query_documents(
            query,
            n_results=KNOWLEDGE_SPACE_RESOLUTION_PROBE_LIMIT,
        )
    except Exception:
        probe_results = []

    candidates = _collect_hitl_options(probe_results, "knowledge_space")
    if candidates:
        return candidates
    return _rank_knowledge_space_candidates(query, _collect_knowledge_spaces())[:HITL_OPTION_LIMIT]


def _resolve_knowledge_space_with_llm(query: str, candidates: list[str]) -> dict[str, Any] | None:
    """让模型判断问题最可能属于哪个知识空间。"""
    if len(candidates) <= 1:
        return None

    raw = _run_auxiliary_completion(
        "你是知识库路由器。必须只输出 JSON，不要附加解释。",
        (
            "请根据用户问题判断它最应该归属到哪个知识空间。\n"
            f"候选知识空间：{json.dumps(candidates, ensure_ascii=False)}\n"
            f"用户问题：{query}\n"
            "如果可以唯一确定，返回："
            '{"status":"resolved","knowledge_space":"候选中的某一项","candidates":["候选中的某一项"]}\n'
            "如果存在多个可能，返回："
            '{"status":"ambiguous","knowledge_space":"","candidates":["候选中的多个候选"]}\n'
            "如果无法判断或明显不属于任何候选，返回："
            '{"status":"unknown","knowledge_space":"","candidates":[]}\n'
            "JSON 中的 knowledge_space 和 candidates 必须完全来自候选知识空间原文。"
        ),
    )
    payload = _extract_json_object(raw)
    if not payload:
        return None

    status = str(payload.get("status", "")).strip().lower()
    knowledge_space = str(payload.get("knowledge_space", "") or "").strip()
    raw_candidates = payload.get("candidates", [])
    candidate_set = {candidate for candidate in candidates}
    filtered_candidates = [
        candidate
        for candidate in raw_candidates
        if isinstance(candidate, str) and candidate.strip() in candidate_set
    ]

    if knowledge_space and knowledge_space not in candidate_set:
        knowledge_space = ""

    if status not in {KNOWLEDGE_SPACE_RESOLVED, KNOWLEDGE_SPACE_AMBIGUOUS, KNOWLEDGE_SPACE_UNKNOWN}:
        return None

    return {
        "status": status,
        "knowledge_space": knowledge_space,
        "candidates": filtered_candidates,
    }


def _resolve_knowledge_space(
    query: str,
    inferred_filters: dict[str, str],
    explicit_filters: dict[str, str],
    session_id: str | None = None,
) -> dict[str, Any]:
    """在检索前先确定问题属于哪个知识空间。"""
    cache_suffix = json.dumps(explicit_filters, ensure_ascii=False, sort_keys=True)
    cache_key = _build_cache_key(query, cache_suffix)
    cached_result = _read_session_cache(session_id, "knowledge_space_resolution", cache_key)
    if isinstance(cached_result, dict):
        return {**cached_result, "cache_hit": True}

    explicit_space = str(explicit_filters.get("knowledge_space", "") or "").strip()
    if explicit_space:
        resolved = {
            "status": KNOWLEDGE_SPACE_RESOLVED,
            "knowledge_space": explicit_space,
            "candidates": [explicit_space],
            "reason": "explicit_filter",
        }
        _write_session_cache(session_id, "knowledge_space_resolution", cache_key, resolved)
        return resolved

    inferred_space = str(inferred_filters.get("knowledge_space", "") or "").strip()
    if inferred_space:
        resolved = {
            "status": KNOWLEDGE_SPACE_RESOLVED,
            "knowledge_space": inferred_space,
            "candidates": [inferred_space],
            "reason": "query_match",
        }
        _write_session_cache(session_id, "knowledge_space_resolution", cache_key, resolved)
        return resolved

    knowledge_spaces = _collect_knowledge_spaces()
    if not knowledge_spaces:
        resolved = {
            "status": KNOWLEDGE_SPACE_UNKNOWN,
            "knowledge_space": "",
            "candidates": [],
            "reason": "empty_knowledge_base",
        }
        _write_session_cache(session_id, "knowledge_space_resolution", cache_key, resolved)
        return resolved

    if len(knowledge_spaces) == 1:
        resolved = {
            "status": KNOWLEDGE_SPACE_RESOLVED,
            "knowledge_space": knowledge_spaces[0],
            "candidates": knowledge_spaces,
            "reason": "single_knowledge_space",
        }
        _write_session_cache(session_id, "knowledge_space_resolution", cache_key, resolved)
        return resolved

    llm_result = _resolve_knowledge_space_with_llm(query, knowledge_spaces)
    if llm_result and llm_result.get("status") == KNOWLEDGE_SPACE_RESOLVED:
        resolved = {
            **llm_result,
            "reason": "llm_resolution",
        }
        _write_session_cache(session_id, "knowledge_space_resolution", cache_key, resolved)
        return resolved

    candidate_spaces = _probe_knowledge_space_candidates(query)
    unresolved_status = KNOWLEDGE_SPACE_UNKNOWN
    if llm_result and llm_result.get("status") == KNOWLEDGE_SPACE_AMBIGUOUS:
        unresolved_status = KNOWLEDGE_SPACE_AMBIGUOUS
        candidate_spaces = llm_result.get("candidates") or candidate_spaces

    if not candidate_spaces:
        candidate_spaces = knowledge_spaces[:HITL_OPTION_LIMIT]

    resolved = {
        "status": unresolved_status,
        "knowledge_space": "",
        "candidates": candidate_spaces[:HITL_OPTION_LIMIT],
        "reason": "needs_user_clarification",
    }
    _write_session_cache(session_id, "knowledge_space_resolution", cache_key, resolved)
    return resolved


def _generate_query_variants(query: str, knowledge_space: str = "", session_id: str | None = None) -> tuple[list[str], bool]:
    """把口语问题扩写成更适合知识库检索的多个问法。"""
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return [], False

    cache_key = _build_cache_key(normalized_query, knowledge_space.strip())
    cached_variants = _read_session_cache(session_id, "query_variants", cache_key)
    if isinstance(cached_variants, list) and cached_variants:
        return list(cached_variants), True

    variants = [normalized_query]
    if QUERY_EXPANSION_LIMIT <= 0:
        _write_session_cache(session_id, "query_variants", cache_key, variants)
        return variants, False

    scope_hint = f"当前知识空间：{knowledge_space}\n" if knowledge_space else ""
    raw = _run_auxiliary_completion(
        "你是知识库检索改写器。只输出若干行中文问句，不要编号，不要解释。",
        (
            f"{scope_hint}"
            f"原始问题：{normalized_query}\n"
            f"请生成 {QUERY_EXPANSION_LIMIT} 个与原问题语义等价、但更接近正式文档写法的中文检索问句。\n"
            "要求：\n"
            "1. 不要引入原问题中没有的新事实、新对象或新流程。\n"
            "2. 可以补充同义词、正式术语、模块名称、流程名称。\n"
            "3. 每行一个问句。"
        ),
    )

    if not raw:
        _write_session_cache(session_id, "query_variants", cache_key, variants)
        return variants, False

    for line in raw.splitlines():
        candidate = re.sub(r"^[\-\d\s.、]+", "", line).strip(" \t\"'“”")
        if candidate and candidate not in variants:
            variants.append(candidate)
        if len(variants) >= QUERY_EXPANSION_LIMIT + 1:
            break

    _write_session_cache(session_id, "query_variants", cache_key, variants)
    return variants, False


def _format_context_header(metadata: dict) -> str:
    """把文档元数据整理成上下文头。

    这段头信息会和正文 chunk 一起送给模型，
    帮助模型理解内容来自哪个知识空间、主题或章节。
    """
    header_parts = []
    for label, key in (
        ("知识空间", "knowledge_space"),
        ("分类", "category"),
        ("主题", "topic"),
        ("标签", "tags"),
        ("版本/时效", "version_label"),
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


def _document_match_count(query_terms: list[str], doc: dict) -> int:
    """统计单个候选片段对问题核心词的覆盖数。"""
    if not query_terms:
        return 0

    metadata = doc.get("metadata", {})
    combined = "\n".join(
        [
            str(doc.get("content", "") or ""),
            str(metadata.get("filename", "") or ""),
            str(metadata.get("knowledge_space", "") or ""),
            str(metadata.get("category", "") or ""),
            str(metadata.get("topic", "") or ""),
            str(metadata.get("tags", "") or ""),
            str(metadata.get("section_title", "") or ""),
            str(metadata.get("heading_path", "") or ""),
            str(metadata.get("source_label", "") or ""),
        ]
    )
    normalized = _normalize_text(combined)
    return sum(1 for term in query_terms if term in normalized)


def _has_sufficient_evidence(query: str, documents: list[dict]) -> bool:
    """判断当前召回证据是否足以支持继续作答。

    这里不依赖特定领域词表，只看两个通用信号：
    1. 最佳语义距离是否足够近。
    2. 问题核心词在最终证据中的覆盖是否足够。
    """
    if not documents:
        return False

    best_distance = min(float(doc.get("distance", 1.0)) for doc in documents)
    core_terms = _extract_core_query_terms(query)
    identifier_terms = _extract_explicit_identifier_terms(query)

    if identifier_terms:
        missing_identifiers = [
            term for term in identifier_terms if not any(_document_match_count([term], doc) > 0 for doc in documents)
        ]
        if missing_identifiers:
            return False

    if not core_terms:
        return best_distance <= EVIDENCE_STRONG_DISTANCE_THRESHOLD

    matched_terms = {
        term
        for term in core_terms
        if any(_document_match_count([term], doc) > 0 for doc in documents)
    }
    coverage = len(matched_terms) / max(len(core_terms), 1)

    if best_distance <= EVIDENCE_STRONG_DISTANCE_THRESHOLD:
        return True

    return best_distance <= EVIDENCE_MAX_DISTANCE_THRESHOLD and coverage >= EVIDENCE_MIN_COVERAGE


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
    query_variant_count = int(trace.get("query_variant_count", 1) or 1)
    knowledge_space_resolution = trace.get("knowledge_space_resolution", {}) or {}

    if knowledge_space_resolution.get("status") == KNOWLEDGE_SPACE_RESOLVED:
        knowledge_space = str(knowledge_space_resolution.get("knowledge_space", "") or "").strip()
        if knowledge_space:
            steps.append(f"已确认问题归属到知识空间“{knowledge_space}”。")
        if knowledge_space_resolution.get("cache_hit"):
            steps.append("已复用当前会话中的知识空间判定结果。")

    if trace.get("used_explicit_filters"):
        steps.append("已按你指定的知识范围限定检索。")
    elif trace.get("used_metadata_filters"):
        steps.append("已识别问题中的文档范围，正在限定检索范围。")
    else:
        steps.append("已完成问题理解，正在检索相关内容。")

    if query_variant_count > 1:
        steps.append(f"已将口语问题扩展为 {query_variant_count} 个相近检索问法。")
    if trace.get("query_variants_cache_hit"):
        steps.append("已复用当前会话中的问题扩写结果。")
    if trace.get("retrieval_cache_hit"):
        steps.append("已复用当前会话中的检索结果。")

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


def _collect_hitl_options(documents: list[dict], field: str) -> list[str]:
    """按命中频次和距离为澄清问题收集候选选项。"""
    ranked: dict[str, tuple[int, float]] = {}

    for doc in documents:
        metadata = doc.get("metadata", {})
        value = str(metadata.get(field, "") or "").strip()
        if not value:
            continue

        distance = float(doc.get("distance", 1.0))
        current = ranked.get(value)
        if current is None:
            ranked[value] = (1, distance)
            continue

        count, best_distance = current
        ranked[value] = (count + 1, min(best_distance, distance))

    ordered = sorted(
        ranked.items(),
        key=lambda item: (-item[1][0], item[1][1], item[0]),
    )
    return [value for value, _ in ordered[:HITL_OPTION_LIMIT]]


def build_hitl_clarification(trace: dict[str, Any]) -> dict[str, Any] | None:
    """当检索来源存在歧义时，生成需要用户二次确认的澄清问题。"""
    knowledge_space_resolution = trace.get("knowledge_space_resolution", {}) or {}
    if knowledge_space_resolution.get("status") in {KNOWLEDGE_SPACE_AMBIGUOUS, KNOWLEDGE_SPACE_UNKNOWN}:
        options = [
            {
                "field": "knowledge_space",
                "value": option,
                "label": f"知识空间：{option}",
            }
            for option in knowledge_space_resolution.get("candidates", [])
            if str(option).strip()
        ]

        question = "当前存在多个知识库，我还不能确定你的问题属于哪个知识空间。请先选择一个明确的知识空间。"
        if knowledge_space_resolution.get("status") == KNOWLEDGE_SPACE_UNKNOWN:
            question = "我暂时无法判断你的问题属于哪个知识空间，或者它可能不在现有知识库内。请先明确你要查询的知识空间。"

        return {
            "question": question,
            "options": options[:HITL_OPTION_LIMIT],
        }

    documents = list(trace.get("documents", []))
    if len(documents) <= 1:
        return None

    metadata_filters = trace.get("metadata_filters", {}) or {}
    if metadata_filters.get("knowledge_space") and metadata_filters.get("category"):
        return None

    best_distance = min(float(doc.get("distance", 1.0)) for doc in documents)
    knowledge_space_options = _collect_hitl_options(documents, "knowledge_space")
    category_options = _collect_hitl_options(documents, "category")

    missing_space_filter = not str(metadata_filters.get("knowledge_space", "")).strip()
    missing_category_filter = not str(metadata_filters.get("category", "")).strip()

    ambiguous_space = missing_space_filter and len(knowledge_space_options) > 1
    ambiguous_category = missing_category_filter and len(category_options) > 1

    if not ambiguous_space and not ambiguous_category:
        return None

    if best_distance <= HITL_DISTANCE_THRESHOLD and not (ambiguous_space and ambiguous_category):
        return None

    if ambiguous_space and ambiguous_category:
        question = "我检索到的内容分散在多个知识空间和分类里，暂时无法确认你要问的是哪一类。请先选择更具体的范围。"
    elif ambiguous_space:
        question = "当前命中的内容来自多个知识空间，我暂时无法确认应该使用哪一个知识空间。请先选择范围。"
    else:
        question = "当前命中的内容落在多个分类里，我暂时无法确认应该采用哪一类资料。请先选择分类。"

    options: list[dict[str, str]] = []
    if ambiguous_space:
        options.extend(
            {
                "field": "knowledge_space",
                "value": option,
                "label": f"知识空间：{option}",
            }
            for option in knowledge_space_options
        )

    if ambiguous_category:
        options.extend(
            {
                "field": "category",
                "value": option,
                "label": f"分类：{option}",
            }
            for option in category_options
        )

    return {
        "question": question,
        "options": options[: HITL_OPTION_LIMIT * 2],
    }


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


def _query_documents_with_variants(
    query_variants: list[str],
    n_results: int,
    metadata_filters: dict[str, str] | None = None,
) -> list[dict]:
    """对多个问法并行做召回，并按 chunk 去重合并。"""
    merged: dict[tuple[str, int, str], dict[str, Any]] = {}

    for variant in query_variants:
        results = vector_store.query_documents(
            variant,
            n_results=n_results,
            metadata_filters=metadata_filters,
        )
        for result in results:
            metadata = result.get("metadata", {})
            key = (
                str(metadata.get("doc_id", "") or metadata.get("filename", "") or ""),
                int(metadata.get("chunk_index", 0) or 0),
                str(result.get("content", "") or ""),
            )
            existing = merged.get(key)
            matched_queries = list(existing.get("matched_queries", [])) if existing else []
            if variant not in matched_queries:
                matched_queries.append(variant)

            best_result = result
            if existing is not None and float(existing.get("distance", 1.0)) <= float(result.get("distance", 1.0)):
                best_result = existing

            merged[key] = {
                **best_result,
                "matched_queries": matched_queries,
            }

    merged_results = list(merged.values())
    merged_results.sort(
        key=lambda item: (
            -len(item.get("matched_queries", [])),
            float(item.get("distance", 1.0)),
        )
    )
    return merged_results


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
    explicit_metadata_filters: dict[str, str] | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """执行完整检索流程，并返回可追踪的中间状态。

    这个 trace 会被聊天流式接口复用，用于展示“已召回多少条、过滤后还剩多少条”等进度信息。
    """
    normalized_explicit_filters = _normalize_explicit_metadata_filters(explicit_metadata_filters)
    trace_cache_key = _build_cache_key(
        query,
        json.dumps(
            {
                "initial_n_results": initial_n_results,
                "final_n_results": final_n_results,
                "explicit_filters": normalized_explicit_filters,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
    cached_trace = _read_session_cache(session_id, "retrieval_trace", trace_cache_key)
    if isinstance(cached_trace, dict):
        reused_trace = copy.deepcopy(cached_trace)
        reused_trace["retrieval_cache_hit"] = True
        return reused_trace

    inferred_metadata_filters = _infer_metadata_filters(query)
    explicit_filters = normalized_explicit_filters
    knowledge_space_resolution = _resolve_knowledge_space(
        query,
        inferred_metadata_filters,
        explicit_filters,
        session_id=session_id,
    )

    if (
        knowledge_space_resolution.get("status") != KNOWLEDGE_SPACE_RESOLVED
        and len(_collect_knowledge_spaces()) > 1
    ):
        trace = {
            "documents": [],
            "rerank_mode": RERANK_MODE_LOCAL,
            "initial_hit_count": 0,
            "filtered_hit_count": 0,
            "final_hit_count": 0,
            "metadata_filters": explicit_filters,
            "used_metadata_filters": bool(explicit_filters),
            "used_explicit_filters": bool(explicit_filters),
            "fallback_without_filters": False,
            "knowledge_space_resolution": knowledge_space_resolution,
            "query_variants": [query],
            "query_variant_count": 1,
            "query_variants_cache_hit": False,
            "retrieval_cache_hit": False,
        }
        _write_session_cache(session_id, "retrieval_trace", trace_cache_key, copy.deepcopy(trace))
        return trace

    metadata_filters = _merge_metadata_filters(inferred_metadata_filters, explicit_filters)
    if (
        knowledge_space_resolution.get("status") == KNOWLEDGE_SPACE_RESOLVED
        and not metadata_filters.get("knowledge_space")
    ):
        metadata_filters["knowledge_space"] = str(knowledge_space_resolution.get("knowledge_space", "") or "")

    query_variants, query_variants_cache_hit = _generate_query_variants(
        query,
        str(metadata_filters.get("knowledge_space", "") or ""),
        session_id=session_id,
    )
    results = _query_documents_with_variants(
        query_variants,
        n_results=initial_n_results,
        metadata_filters=metadata_filters,
    )
    fallback_without_filters = False

    # 如果基于元数据过滤没有召回结果，就自动回退到无过滤检索，避免误过滤导致完全答不出来。
    if not results and metadata_filters and not explicit_filters:
        fallback_without_filters = True
        results = _query_documents_with_variants(query_variants, n_results=initial_n_results)

    if not results:
        trace = {
            "documents": [],
            "rerank_mode": RERANK_MODE_LOCAL,
            "initial_hit_count": 0,
            "filtered_hit_count": 0,
            "final_hit_count": 0,
            "metadata_filters": metadata_filters,
            "used_metadata_filters": bool(metadata_filters),
            "used_explicit_filters": bool(explicit_filters),
            "fallback_without_filters": fallback_without_filters,
            "knowledge_space_resolution": knowledge_space_resolution,
            "query_variants": query_variants,
            "query_variant_count": len(query_variants),
            "query_variants_cache_hit": query_variants_cache_hit,
            "retrieval_cache_hit": False,
        }
        _write_session_cache(session_id, "retrieval_trace", trace_cache_key, copy.deepcopy(trace))
        return trace

    filtered = [result for result in results if result["distance"] < RETRIEVAL_THRESHOLD]

    if not filtered:
        trace = {
            "documents": [],
            "rerank_mode": RERANK_MODE_LOCAL,
            "initial_hit_count": len(results),
            "filtered_hit_count": 0,
            "final_hit_count": 0,
            "metadata_filters": metadata_filters,
            "used_metadata_filters": bool(metadata_filters),
            "used_explicit_filters": bool(explicit_filters),
            "fallback_without_filters": fallback_without_filters,
            "knowledge_space_resolution": knowledge_space_resolution,
            "query_variants": query_variants,
            "query_variant_count": len(query_variants),
            "query_variants_cache_hit": query_variants_cache_hit,
            "retrieval_cache_hit": False,
        }
        _write_session_cache(session_id, "retrieval_trace", trace_cache_key, copy.deepcopy(trace))
        return trace

    reranked, rerank_mode = _rerank_documents(query, filtered, limit=final_n_results)
    if not _has_sufficient_evidence(query, reranked):
        trace = {
            "documents": [],
            "rerank_mode": rerank_mode,
            "initial_hit_count": len(results),
            "filtered_hit_count": len(filtered),
            "final_hit_count": 0,
            "metadata_filters": metadata_filters,
            "used_metadata_filters": bool(metadata_filters),
            "used_explicit_filters": bool(explicit_filters),
            "fallback_without_filters": fallback_without_filters,
            "knowledge_space_resolution": knowledge_space_resolution,
            "query_variants": query_variants,
            "query_variant_count": len(query_variants),
            "query_variants_cache_hit": query_variants_cache_hit,
            "retrieval_cache_hit": False,
        }
        _write_session_cache(session_id, "retrieval_trace", trace_cache_key, copy.deepcopy(trace))
        return trace

    trace = {
        "documents": reranked,
        "rerank_mode": rerank_mode,
        "initial_hit_count": len(results),
        "filtered_hit_count": len(filtered),
        "final_hit_count": len(reranked),
        "metadata_filters": metadata_filters,
        "used_metadata_filters": bool(metadata_filters),
        "used_explicit_filters": bool(explicit_filters),
        "fallback_without_filters": fallback_without_filters,
        "knowledge_space_resolution": knowledge_space_resolution,
        "query_variants": query_variants,
        "query_variant_count": len(query_variants),
        "query_variants_cache_hit": query_variants_cache_hit,
        "retrieval_cache_hit": False,
    }
    _write_session_cache(session_id, "retrieval_trace", trace_cache_key, copy.deepcopy(trace))
    return trace


def retrieve_relevant_documents_with_mode(
    query: str,
    initial_n_results: int = INITIAL_RETRIEVAL_LIMIT,
    final_n_results: int = FINAL_CONTEXT_LIMIT,
    explicit_metadata_filters: dict[str, str] | None = None,
    session_id: str | None = None,
) -> tuple[list[dict], str]:
    """返回最终可用文档，以及 rerank 采用的模式。"""
    trace = retrieve_relevant_documents_trace(
        query,
        initial_n_results=initial_n_results,
        final_n_results=final_n_results,
        explicit_metadata_filters=explicit_metadata_filters,
        session_id=session_id,
    )
    return list(trace["documents"]), str(trace["rerank_mode"])


def retrieve_relevant_documents(
    query: str,
    initial_n_results: int = INITIAL_RETRIEVAL_LIMIT,
    final_n_results: int = FINAL_CONTEXT_LIMIT,
    explicit_metadata_filters: dict[str, str] | None = None,
    session_id: str | None = None,
) -> list[dict]:
    """兼容型包装函数，只关心最终文档列表时使用。"""
    relevant, _ = retrieve_relevant_documents_with_mode(
        query,
        initial_n_results=initial_n_results,
        final_n_results=final_n_results,
        explicit_metadata_filters=explicit_metadata_filters,
        session_id=session_id,
    )
    return relevant


def build_source_payload(
    query: str,
    n_results: int = FINAL_SOURCE_LIMIT,
    explicit_metadata_filters: dict[str, str] | None = None,
    session_id: str | None = None,
) -> tuple[list[dict], str]:
    """把检索结果转成前端来源卡片需要的轻量结构。"""
    trace = retrieve_relevant_documents_trace(
        query,
        initial_n_results=INITIAL_RETRIEVAL_LIMIT,
        final_n_results=n_results,
        explicit_metadata_filters=explicit_metadata_filters,
        session_id=session_id,
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
                "knowledge_space": metadata.get("knowledge_space", ""),
                "category": metadata.get("category", ""),
                "topic": metadata.get("topic", ""),
                "tags": metadata.get("tags", ""),
                "version_label": metadata.get("version_label", ""),
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
    explicit_metadata_filters: dict[str, str] | None = None,
    session_id: str | None = None,
) -> tuple[list[dict], dict[str, Any]]:
    """同时返回来源摘要和完整 trace，供流式接口展示检索进度。"""
    trace = retrieve_relevant_documents_trace(
        query,
        initial_n_results=INITIAL_RETRIEVAL_LIMIT,
        final_n_results=n_results,
        explicit_metadata_filters=explicit_metadata_filters,
        session_id=session_id,
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
                "knowledge_space": metadata.get("knowledge_space", ""),
                "category": metadata.get("category", ""),
                "topic": metadata.get("topic", ""),
                "tags": metadata.get("tags", ""),
                "version_label": metadata.get("version_label", ""),
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


def build_source_summaries(
    query: str,
    n_results: int = FINAL_SOURCE_LIMIT,
    explicit_metadata_filters: dict[str, str] | None = None,
    session_id: str | None = None,
) -> list[dict]:
    """仅返回来源摘要列表的简化入口。"""
    summaries, _ = build_source_payload(
        query,
        n_results=n_results,
        explicit_metadata_filters=explicit_metadata_filters,
        session_id=session_id,
    )
    return summaries


def retrieve_from_knowledge_base(
    query: str,
    explicit_metadata_filters: dict[str, str] | None = None,
    session_id: str | None = None,
) -> str:
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
        explicit_metadata_filters=explicit_metadata_filters,
        session_id=session_id,
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


def create_rag_agent(
    explicit_metadata_filters: dict[str, str] | None = None,
    session_id: str | None = None,
) -> Agent:
    """创建 ADK RAG Agent。

    Agent 本身只做一件事：
    调用 retrieve_from_knowledge_base 拿上下文，再按照 SYSTEM_INSTRUCTION 输出最终答案。
    """
    normalized_filters = _normalize_explicit_metadata_filters(explicit_metadata_filters)

    def retrieval_tool(query: str) -> str:
        return retrieve_from_knowledge_base(
            query,
            explicit_metadata_filters=normalized_filters,
            session_id=session_id,
        )

    return Agent(
        name="rag_agent",
        model=_build_llm(),
        description="Knowledge base Q&A agent that only answers based on uploaded documents.",
        instruction=SYSTEM_INSTRUCTION,
        tools=[retrieval_tool],
    )
