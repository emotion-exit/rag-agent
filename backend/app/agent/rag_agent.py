"""RAG 检索编排与 Agent 构建。"""

from __future__ import annotations

import copy
import json
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from google.adk.agents import Agent

from app.agent.llm import build_llm
from app.agent.prompts import (
    CONTEXT_ONLY_INSTRUCTION_TEMPLATE,
    NO_KNOWLEDGE_BASE_ANSWER,
    NO_KNOWLEDGE_BASE_CONTEXT,
    get_answer_system_instruction,
)
from app.agent.retrieval_support import (
    EVIDENCE_MAX_DISTANCE_THRESHOLD,
    EVIDENCE_MIN_COVERAGE,
    EVIDENCE_STRONG_DISTANCE_THRESHOLD,
    HITL_DISTANCE_THRESHOLD,
    HITL_OPTION_LIMIT,
    KNOWLEDGE_SPACE_AMBIGUOUS,
    KNOWLEDGE_SPACE_RESOLVED,
    KNOWLEDGE_SPACE_UNKNOWN,
    MAX_CHUNKS_PER_DOCUMENT,
    RERANK_MODE_LOCAL,
    RERANK_MODE_MODEL,
    RETRIEVAL_THRESHOLD,
    build_cache_key,
    build_retrieval_runtime_config_snapshot,
    collect_knowledge_spaces,
    emit_retrieval_progress,
    expand_metadata_filters_for_hierarchy,
    extract_core_query_terms,
    extract_explicit_identifier_terms,
    extract_query_term_groups,
    extract_query_terms,
    format_context_header,
    generate_query_variants,
    get_final_context_limit,
    get_final_source_limit,
    get_initial_retrieval_limit,
    infer_metadata_filters,
    merge_metadata_filters,
    metadata_match_count,
    normalize_explicit_metadata_filters,
    normalize_text,
    read_session_cache,
    resolve_knowledge_space,
    summarize_excerpt,
    write_session_cache,
)
from app.services import vector_store
from app.services.auth import get_current_user
from app.services.knowledge_spaces import list_accessible_space_ids
from app.services.reranker import rerank_documents


def _document_match_count(query_terms: list[str], doc: dict) -> int:
    if not query_terms:
        return 0

    metadata = doc.get("metadata", {})
    combined = "\n".join(
        [
            str(doc.get("content", "") or ""),
            str(metadata.get("filename", "") or ""),
            str(metadata.get("knowledge_space", "") or ""),
            str(metadata.get("tags", "") or ""),
            str(metadata.get("section_title", "") or ""),
            str(metadata.get("heading_path", "") or ""),
            str(metadata.get("source_label", "") or ""),
        ]
    )
    normalized = normalize_text(combined)
    return sum(1 for term in query_terms if term in normalized)


def _has_sufficient_evidence(query: str, documents: list[dict]) -> bool:
    if not documents:
        return False

    best_distance = min(float(doc.get("distance", 1.0)) for doc in documents)
    core_terms = extract_core_query_terms(query)
    concept_groups = extract_query_term_groups(query)
    identifier_terms = extract_explicit_identifier_terms(query)

    if identifier_terms:
        missing_identifiers = [
            term for term in identifier_terms if not any(_document_match_count([term], doc) > 0 for doc in documents)
        ]
        if missing_identifiers:
            return False

    if not core_terms:
        return best_distance <= EVIDENCE_STRONG_DISTANCE_THRESHOLD

    matched_groups = 0
    for group in concept_groups or [[term] for term in core_terms]:
        if any(_document_match_count(group, doc) > 0 for doc in documents):
            matched_groups += 1

    coverage_denominator = len(concept_groups) or max(len(core_terms), 1)
    coverage = matched_groups / max(coverage_denominator, 1)

    if best_distance <= EVIDENCE_STRONG_DISTANCE_THRESHOLD:
        return True

    return best_distance <= EVIDENCE_MAX_DISTANCE_THRESHOLD and coverage >= EVIDENCE_MIN_COVERAGE


def _score_document(query_terms: list[str], doc: dict) -> tuple[float, int]:
    content = normalize_text(doc.get("content", ""))
    distance = float(doc.get("distance", 1.0))
    semantic_score = max(0.0, 1.0 - distance)

    if not query_terms:
        return semantic_score, 0

    keyword_hits = sum(1 for term in query_terms if term in content)
    weighted_hits = sum(len(term) for term in query_terms if term in content)
    keyword_score = min(weighted_hits / max(len("".join(query_terms)), 1), 1.0)
    meta_hits = metadata_match_count(query_terms, doc.get("metadata", {}))
    metadata_score = min(meta_hits / max(len(query_terms), 1), 1.0)
    final_score = semantic_score * 0.55 + keyword_score * 0.3 + metadata_score * 0.15
    return final_score, keyword_hits + meta_hits


def _build_rerank_status(mode: str) -> str:
    if mode == RERANK_MODE_MODEL:
        return "已完成候选片段排序。"
    return "已完成候选片段排序。"


def build_retrieval_progress_steps(trace: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    query_variant_count = int(trace.get("query_variant_count", 1) or 1)
    query_expansion_count = max(query_variant_count - 1, 0)
    knowledge_space_resolution = trace.get("knowledge_space_resolution", {}) or {}
    expanded_knowledge_space_count = int(trace.get("expanded_knowledge_space_count", 0) or 0)

    if knowledge_space_resolution.get("status") == KNOWLEDGE_SPACE_RESOLVED:
        knowledge_space = str(knowledge_space_resolution.get("knowledge_space", "") or "").strip()
        if knowledge_space:
            steps.append(f"已确认问题归属到知识空间“{knowledge_space}”。")
        if knowledge_space_resolution.get("cache_hit"):
            steps.append("已复用当前会话中的知识空间判定结果。")

    if trace.get("used_explicit_filters"):
        if expanded_knowledge_space_count > 1:
            steps.append(f"已按你指定的知识空间层级限定检索，覆盖 {expanded_knowledge_space_count} 个空间。")
        else:
            steps.append("已按你指定的知识范围限定检索。")
    elif trace.get("used_metadata_filters"):
        steps.append("已识别问题中的文档范围，正在限定检索范围。")
    else:
        steps.append("已完成问题理解，正在检索相关内容。")

    if query_expansion_count > 0:
        steps.append(f"已生成 {query_expansion_count} 个扩写问法用于辅助检索。")
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

    ordered = sorted(ranked.items(), key=lambda item: (-item[1][0], item[1][1], item[0]))
    return [value for value, _ in ordered[:HITL_OPTION_LIMIT]]


def build_hitl_clarification(trace: dict[str, Any]) -> dict[str, Any] | None:
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

        return {"question": question, "options": options[:HITL_OPTION_LIMIT]}

    documents = list(trace.get("documents", []))
    if len(documents) <= 1:
        return None

    metadata_filters = trace.get("metadata_filters", {}) or {}
    if metadata_filters.get("knowledge_space"):
        return None

    best_distance = min(float(doc.get("distance", 1.0)) for doc in documents)
    knowledge_space_options = _collect_hitl_options(documents, "knowledge_space")
    missing_space_filter = not str(metadata_filters.get("knowledge_space", "")).strip()
    ambiguous_space = missing_space_filter and len(knowledge_space_options) > 1

    if not ambiguous_space or best_distance <= HITL_DISTANCE_THRESHOLD:
        return None

    question = "当前命中的内容来自多个知识库，我暂时无法确认应该使用哪一个知识库。请先选择范围。"
    options = [
        {
            "field": "knowledge_space",
            "value": option,
            "label": f"知识库：{option}",
        }
        for option in knowledge_space_options
    ]

    return {"question": question, "options": options[: HITL_OPTION_LIMIT * 2]}


def _fallback_rerank_documents(query: str, documents: list[dict]) -> list[dict]:
    query_terms = extract_query_terms(query)
    scored_docs: list[dict] = []

    for doc in documents:
        rerank_score, keyword_hits = _score_document(query_terms, doc)
        scored_docs.append({**doc, "rerank_score": rerank_score, "keyword_hits": keyword_hits})

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
    merged: dict[tuple[str, int, str], dict[str, Any]] = {}
    user = get_current_user(required=False)
    accessible_space_ids = list_accessible_space_ids(user) if user else []

    for variant in query_variants:
        results = vector_store.query_documents(
            variant,
            n_results=n_results,
            metadata_filters=metadata_filters,
            accessible_space_ids=accessible_space_ids,
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

            merged[key] = {**best_result, "matched_queries": matched_queries}

    merged_results = list(merged.values())
    merged_results.sort(
        key=lambda item: (-len(item.get("matched_queries", [])), float(item.get("distance", 1.0)))
    )
    return merged_results[: max(int(n_results or 0), 1)]


def _rerank_documents(query: str, documents: list[dict], limit: int) -> tuple[list[dict], str]:
    scored_docs: list[dict]
    rerank_mode = RERANK_MODE_MODEL

    try:
        rerank_results = rerank_documents(query, [doc.get("content", "") for doc in documents])

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
    initial_n_results: int | None = None,
    final_n_results: int | None = None,
    explicit_metadata_filters: dict[str, str] | None = None,
    session_id: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    normalized_explicit_filters = normalize_explicit_metadata_filters(explicit_metadata_filters)
    initial_n_results = initial_n_results or get_initial_retrieval_limit()
    final_n_results = final_n_results or get_final_context_limit()
    runtime_config_snapshot = build_retrieval_runtime_config_snapshot()
    trace_cache_key = build_cache_key(
        query,
        json.dumps(
            {
                "initial_n_results": initial_n_results,
                "final_n_results": final_n_results,
                "explicit_filters": normalized_explicit_filters,
                "runtime_config": runtime_config_snapshot,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
    cached_trace = read_session_cache(session_id, "retrieval_trace", trace_cache_key)
    if isinstance(cached_trace, dict):
        reused_trace = copy.deepcopy(cached_trace)
        reused_trace["retrieval_cache_hit"] = True
        emit_retrieval_progress(progress_callback, "已复用当前会话中的检索结果。")
        return reused_trace

    emit_retrieval_progress(progress_callback, "正在确认问题所属的知识空间。")
    inferred_metadata_filters = infer_metadata_filters(query)
    explicit_filters = normalized_explicit_filters
    knowledge_space_resolution = resolve_knowledge_space(
        query,
        inferred_metadata_filters,
        explicit_filters,
        session_id=session_id,
    )

    if knowledge_space_resolution.get("cache_hit"):
        emit_retrieval_progress(progress_callback, "已复用当前会话中的知识空间判定结果。")
    elif knowledge_space_resolution.get("status") == KNOWLEDGE_SPACE_RESOLVED:
        resolved_space = str(knowledge_space_resolution.get("knowledge_space", "") or "").strip()
        if resolved_space:
            emit_retrieval_progress(progress_callback, f"已确认问题归属到知识空间“{resolved_space}”。")
    else:
        emit_retrieval_progress(progress_callback, "知识空间仍需进一步确认。")

    if (
        knowledge_space_resolution.get("status") != KNOWLEDGE_SPACE_RESOLVED
        and len(collect_knowledge_spaces()) > 1
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
        write_session_cache(session_id, "retrieval_trace", trace_cache_key, copy.deepcopy(trace))
        return trace

    metadata_filters = merge_metadata_filters(inferred_metadata_filters, explicit_filters)
    if (
        knowledge_space_resolution.get("status") == KNOWLEDGE_SPACE_RESOLVED
        and not metadata_filters.get("knowledge_space")
    ):
        metadata_filters["knowledge_space"] = str(knowledge_space_resolution.get("knowledge_space", "") or "")

    effective_metadata_filters = expand_metadata_filters_for_hierarchy(metadata_filters)
    effective_knowledge_space_filter = effective_metadata_filters.get("knowledge_space")
    expanded_knowledge_space_count = 0
    if isinstance(effective_knowledge_space_filter, list):
        expanded_knowledge_space_count = len(effective_knowledge_space_filter)
    elif str(effective_knowledge_space_filter or "").strip():
        expanded_knowledge_space_count = 1

    emit_retrieval_progress(progress_callback, "正在生成检索问法。")
    query_variants, query_variants_cache_hit = generate_query_variants(
        query,
        str(metadata_filters.get("knowledge_space", "") or ""),
        session_id=session_id,
    )
    if query_variants_cache_hit:
        emit_retrieval_progress(progress_callback, "已复用当前会话中的问题扩写结果。")
    elif len(query_variants) > 1:
        emit_retrieval_progress(progress_callback, f"已生成 {len(query_variants) - 1} 个扩写问法用于辅助检索。")
    else:
        emit_retrieval_progress(progress_callback, "当前问题将直接用于检索。")

    emit_retrieval_progress(progress_callback, "正在向量检索相关片段。")
    results = _query_documents_with_variants(
        query_variants,
        n_results=initial_n_results,
        metadata_filters=effective_metadata_filters,
    )
    fallback_without_filters = False

    if not results and metadata_filters and not explicit_filters:
        fallback_without_filters = True
        emit_retrieval_progress(progress_callback, "限定范围内未命中内容，正在放宽检索范围重试。")
        results = _query_documents_with_variants(query_variants, n_results=initial_n_results)

    if results:
        emit_retrieval_progress(progress_callback, f"已完成初步召回，找到 {len(results)} 个候选片段。")
    else:
        emit_retrieval_progress(progress_callback, "初步召回未找到相关片段。")

    if not results:
        trace = {
            "documents": [],
            "rerank_mode": RERANK_MODE_LOCAL,
            "initial_hit_count": 0,
            "filtered_hit_count": 0,
            "final_hit_count": 0,
            "metadata_filters": metadata_filters,
            "effective_metadata_filters": effective_metadata_filters,
            "used_metadata_filters": bool(metadata_filters),
            "used_explicit_filters": bool(explicit_filters),
            "fallback_without_filters": fallback_without_filters,
            "expanded_knowledge_space_count": expanded_knowledge_space_count,
            "knowledge_space_resolution": knowledge_space_resolution,
            "query_variants": query_variants,
            "query_variant_count": len(query_variants),
            "query_variants_cache_hit": query_variants_cache_hit,
            "retrieval_cache_hit": False,
        }
        write_session_cache(session_id, "retrieval_trace", trace_cache_key, copy.deepcopy(trace))
        return trace

    filtered = [result for result in results if result["distance"] < RETRIEVAL_THRESHOLD]

    if filtered:
        emit_retrieval_progress(progress_callback, f"已完成相关度过滤，保留 {len(filtered)} 个候选片段。")
    else:
        emit_retrieval_progress(progress_callback, "候选片段相关度不足，未保留可用内容。")

    if not filtered:
        trace = {
            "documents": [],
            "rerank_mode": RERANK_MODE_LOCAL,
            "initial_hit_count": len(results),
            "filtered_hit_count": 0,
            "final_hit_count": 0,
            "metadata_filters": metadata_filters,
            "effective_metadata_filters": effective_metadata_filters,
            "used_metadata_filters": bool(metadata_filters),
            "used_explicit_filters": bool(explicit_filters),
            "fallback_without_filters": fallback_without_filters,
            "expanded_knowledge_space_count": expanded_knowledge_space_count,
            "knowledge_space_resolution": knowledge_space_resolution,
            "query_variants": query_variants,
            "query_variant_count": len(query_variants),
            "query_variants_cache_hit": query_variants_cache_hit,
            "retrieval_cache_hit": False,
        }
        write_session_cache(session_id, "retrieval_trace", trace_cache_key, copy.deepcopy(trace))
        return trace

    emit_retrieval_progress(progress_callback, "正在排序候选片段。")
    reranked, rerank_mode = _rerank_documents(query, filtered, limit=final_n_results)
    emit_retrieval_progress(progress_callback, _build_rerank_status(rerank_mode))
    if not _has_sufficient_evidence(query, reranked):
        emit_retrieval_progress(progress_callback, "候选内容证据不足，无法直接生成答案。")
        trace = {
            "documents": [],
            "rerank_mode": rerank_mode,
            "initial_hit_count": len(results),
            "filtered_hit_count": len(filtered),
            "final_hit_count": 0,
            "metadata_filters": metadata_filters,
            "effective_metadata_filters": effective_metadata_filters,
            "used_metadata_filters": bool(metadata_filters),
            "used_explicit_filters": bool(explicit_filters),
            "fallback_without_filters": fallback_without_filters,
            "expanded_knowledge_space_count": expanded_knowledge_space_count,
            "knowledge_space_resolution": knowledge_space_resolution,
            "query_variants": query_variants,
            "query_variant_count": len(query_variants),
            "query_variants_cache_hit": query_variants_cache_hit,
            "retrieval_cache_hit": False,
        }
        write_session_cache(session_id, "retrieval_trace", trace_cache_key, copy.deepcopy(trace))
        return trace

    emit_retrieval_progress(progress_callback, f"已选取 {len(reranked)} 个片段用于生成答案。")

    trace = {
        "documents": reranked,
        "rerank_mode": rerank_mode,
        "initial_hit_count": len(results),
        "filtered_hit_count": len(filtered),
        "final_hit_count": len(reranked),
        "metadata_filters": metadata_filters,
        "effective_metadata_filters": effective_metadata_filters,
        "used_metadata_filters": bool(metadata_filters),
        "used_explicit_filters": bool(explicit_filters),
        "fallback_without_filters": fallback_without_filters,
        "expanded_knowledge_space_count": expanded_knowledge_space_count,
        "knowledge_space_resolution": knowledge_space_resolution,
        "query_variants": query_variants,
        "query_variant_count": len(query_variants),
        "query_variants_cache_hit": query_variants_cache_hit,
        "retrieval_cache_hit": False,
    }
    write_session_cache(session_id, "retrieval_trace", trace_cache_key, copy.deepcopy(trace))
    return trace


def retrieve_relevant_documents_with_mode(
    query: str,
    initial_n_results: int | None = None,
    final_n_results: int | None = None,
    explicit_metadata_filters: dict[str, str] | None = None,
    session_id: str | None = None,
) -> tuple[list[dict], str]:
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
    initial_n_results: int | None = None,
    final_n_results: int | None = None,
    explicit_metadata_filters: dict[str, str] | None = None,
    session_id: str | None = None,
) -> list[dict]:
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
    n_results: int | None = None,
    explicit_metadata_filters: dict[str, str] | None = None,
    session_id: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[list[dict], str]:
    source_limit = n_results or get_final_source_limit()
    trace = retrieve_relevant_documents_trace(
        query,
        initial_n_results=get_initial_retrieval_limit(),
        final_n_results=get_final_context_limit(),
        explicit_metadata_filters=explicit_metadata_filters,
        session_id=session_id,
        progress_callback=progress_callback,
    )
    relevant = list(trace["documents"])[:source_limit]
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
                "tags": metadata.get("tags", ""),
                "source_type": metadata.get("source_type", "text"),
                "source_label": metadata.get("source_label", "正文文本"),
                "source_page": metadata.get("source_page", 0),
                "section_title": metadata.get("section_title", ""),
                "heading_path": metadata.get("heading_path", ""),
                "image_count": int(metadata.get("image_count", 0) or 0),
                "summary": summarize_excerpt(content),
            }
        )

    return summaries, rerank_mode


def build_source_payload_with_trace(
    query: str,
    n_results: int | None = None,
    explicit_metadata_filters: dict[str, str] | None = None,
    session_id: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[list[dict], dict[str, Any]]:
    source_limit = n_results or get_final_source_limit()
    trace = retrieve_relevant_documents_trace(
        query,
        initial_n_results=get_initial_retrieval_limit(),
        final_n_results=get_final_context_limit(),
        explicit_metadata_filters=explicit_metadata_filters,
        session_id=session_id,
        progress_callback=progress_callback,
    )

    summaries = []
    for index, doc in enumerate(list(trace["documents"])[:source_limit], 1):
        metadata = doc.get("metadata", {})
        content = doc.get("content", "")
        summaries.append(
            {
                "index": index,
                "doc_id": metadata.get("doc_id", ""),
                "filename": metadata.get("filename", "未知文档"),
                "chunk_index": metadata.get("chunk_index", 0),
                "knowledge_space": metadata.get("knowledge_space", ""),
                "tags": metadata.get("tags", ""),
                "source_type": metadata.get("source_type", "text"),
                "source_label": metadata.get("source_label", "正文文本"),
                "source_page": metadata.get("source_page", 0),
                "section_title": metadata.get("section_title", ""),
                "heading_path": metadata.get("heading_path", ""),
                "image_count": int(metadata.get("image_count", 0) or 0),
                "summary": summarize_excerpt(content),
            }
        )

    return summaries, trace


def build_source_summaries(
    query: str,
    n_results: int | None = None,
    explicit_metadata_filters: dict[str, str] | None = None,
    session_id: str | None = None,
) -> list[dict]:
    summaries, _ = build_source_payload(
        query,
        n_results=n_results,
        explicit_metadata_filters=explicit_metadata_filters,
        session_id=session_id,
    )
    return summaries


def build_context_from_documents(documents: list[dict]) -> str:
    if not documents:
        return NO_KNOWLEDGE_BASE_CONTEXT

    context_parts = []
    for index, doc in enumerate(documents, 1):
        metadata = doc["metadata"]
        filename = metadata.get("filename", "未知文档")
        header = format_context_header(metadata)
        if header:
            context_parts.append(f"[来源 {index}: {filename}]\n{header}\n[内容]\n{doc['content']}")
        else:
            context_parts.append(f"[来源 {index}: {filename}]\n[内容]\n{doc['content']}")

    return "\n\n---\n\n".join(context_parts)


def retrieve_from_knowledge_base(
    query: str,
    explicit_metadata_filters: dict[str, str] | None = None,
    session_id: str | None = None,
) -> str:
    if vector_store.collection_count() == 0:
        return "【知识库为空，尚未上传任何文档。】"

    relevant, _ = retrieve_relevant_documents_with_mode(
        query,
        initial_n_results=get_initial_retrieval_limit(),
        final_n_results=get_final_context_limit(),
        explicit_metadata_filters=explicit_metadata_filters,
        session_id=session_id,
    )

    if not relevant:
        return NO_KNOWLEDGE_BASE_CONTEXT

    return build_context_from_documents(relevant)


def create_rag_agent(
    explicit_metadata_filters: dict[str, str] | None = None,
    session_id: str | None = None,
    original_query: str | None = None,
    retrieval_documents: list[dict] | None = None,
) -> Agent:
    normalized_filters = normalize_explicit_metadata_filters(explicit_metadata_filters)
    normalized_original_query = str(original_query or "").strip()
    retrieval_context = build_context_from_documents(list(retrieval_documents or [])) if retrieval_documents else ""

    def retrieval_tool(query: str) -> str:
        requested_query = str(query or "").strip() or normalized_original_query
        retrieval_result = retrieve_from_knowledge_base(
            requested_query,
            explicit_metadata_filters=normalized_filters,
            session_id=session_id,
        )

        if (
            retrieval_result == NO_KNOWLEDGE_BASE_CONTEXT
            and normalized_original_query
            and normalize_text(requested_query) != normalize_text(normalized_original_query)
        ):
            return retrieve_from_knowledge_base(
                normalized_original_query,
                explicit_metadata_filters=normalized_filters,
                session_id=session_id,
            )

        return retrieval_result

    answer_system_instruction = get_answer_system_instruction()
    agent_instruction = answer_system_instruction
    tools = [retrieval_tool]

    if retrieval_context:
        agent_instruction = (
            f"{answer_system_instruction}\n\n"
            + CONTEXT_ONLY_INSTRUCTION_TEMPLATE.format(
                no_answer=NO_KNOWLEDGE_BASE_ANSWER,
                retrieval_context=retrieval_context,
            )
        )
        tools = []

    return Agent(
        name="rag_agent",
        model=build_llm(),
        description="Knowledge base Q&A agent that only answers based on uploaded documents.",
        instruction=agent_instruction,
        tools=tools,
    )
