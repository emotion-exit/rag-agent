from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from app.config import settings
from app.services.auth import get_current_user
from app.services import vector_store
from app.services.knowledge_spaces import list_accessible_space_ids, list_knowledge_spaces
from app.agent.llm import run_auxiliary_completion

RETRIEVAL_THRESHOLD = 0.7
MAX_CHUNKS_PER_DOCUMENT = 2
SOURCE_SUMMARY_LENGTH = 140
HITL_OPTION_LIMIT = 4
HITL_DISTANCE_THRESHOLD = 0.42
EVIDENCE_STRONG_DISTANCE_THRESHOLD = 0.38
EVIDENCE_MAX_DISTANCE_THRESHOLD = 0.55
EVIDENCE_MIN_COVERAGE = 0.5
QUERY_FILTER_FIELDS = ("knowledge_space",)
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
ALLOWED_METADATA_FILTER_FIELDS = ("knowledge_space",)
KNOWLEDGE_SPACE_RESOLVED = "resolved"
KNOWLEDGE_SPACE_AMBIGUOUS = "ambiguous"
KNOWLEDGE_SPACE_UNKNOWN = "unknown"
SESSION_CACHE_MAX_SESSIONS = 64
SESSION_CACHE_MAX_ENTRIES_PER_BUCKET = 128

_SESSION_RETRIEVAL_CACHE: dict[str, dict[str, dict[str, Any]]] = {}


def get_initial_retrieval_limit() -> int:
    return max(int(settings.retrieval_candidate_limit), 1)


def get_final_context_limit() -> int:
    return max(int(settings.retrieval_final_context_limit), 1)


def get_final_source_limit() -> int:
    return max(int(settings.retrieval_source_limit), 1)


def get_query_expansion_limit() -> int:
    return max(int(settings.retrieval_query_expansion_count), 0)


def get_knowledge_space_resolution_probe_limit() -> int:
    return max(get_initial_retrieval_limit(), 8)


def summarize_excerpt(content: str, max_length: int = SOURCE_SUMMARY_LENGTH) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[:max_length].rstrip()}..."


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def extract_query_terms(query: str) -> list[str]:
    normalized = normalize_text(query)
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


def extract_core_query_terms(query: str) -> list[str]:
    normalized = normalize_text(query)
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


def extract_query_term_groups(query: str) -> list[list[str]]:
    normalized = normalize_text(query)
    if not normalized:
        return []

    groups: list[list[str]] = []
    seen_group_keys: set[tuple[str, ...]] = set()

    for token in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", normalized):
        if token in QUERY_STOPWORDS or len(token) <= 1:
            continue

        candidates = [token]
        if re.fullmatch(r"[\u4e00-\u9fff]+", token) and len(token) >= 3:
            for size in range(2, min(len(token), 4) + 1):
                for start in range(0, len(token) - size + 1):
                    piece = token[start : start + size]
                    if piece not in QUERY_STOPWORDS:
                        candidates.append(piece)

        deduped: list[str] = []
        seen_terms: set[str] = set()
        for item in sorted(candidates, key=len, reverse=True):
            if item in seen_terms:
                continue
            seen_terms.add(item)
            deduped.append(item)

        if not deduped:
            continue

        group_key = tuple(deduped)
        if group_key in seen_group_keys:
            continue

        seen_group_keys.add(group_key)
        groups.append(deduped)

    return groups


def extract_explicit_identifier_terms(query: str) -> list[str]:
    normalized = normalize_text(query)
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


def normalize_metadata_value(value: str) -> str:
    return re.sub(r"\s+", "", value.lower())


def extract_json_object(raw_text: str) -> dict[str, Any] | None:
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


def build_cache_key(query: str, suffix: str = "") -> str:
    normalized_query = normalize_text(query)
    return f"{normalized_query}::{suffix}" if suffix else normalized_query


def build_retrieval_runtime_config_snapshot() -> dict[str, Any]:
    return {
        "retrieval_candidate_limit": get_initial_retrieval_limit(),
        "retrieval_final_context_limit": get_final_context_limit(),
        "retrieval_source_limit": get_final_source_limit(),
        "retrieval_query_expansion_count": get_query_expansion_limit(),
        "reranker_request_timeout": settings.get_reranker_timeout(),
    }


def _get_session_cache_bucket(session_id: str | None, bucket_name: str) -> dict[str, Any] | None:
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


def read_session_cache(session_id: str | None, bucket_name: str, cache_key: str) -> Any | None:
    bucket = _get_session_cache_bucket(session_id, bucket_name)
    if bucket is None:
        return None
    return bucket.get(cache_key)


def write_session_cache(session_id: str | None, bucket_name: str, cache_key: str, value: Any) -> None:
    bucket = _get_session_cache_bucket(session_id, bucket_name)
    if bucket is None:
        return

    if cache_key in bucket:
        bucket.pop(cache_key, None)
    bucket[cache_key] = value

    while len(bucket) > SESSION_CACHE_MAX_ENTRIES_PER_BUCKET:
        oldest_key = next(iter(bucket))
        bucket.pop(oldest_key, None)


def normalize_explicit_metadata_filters(metadata_filters: dict[str, str] | None) -> dict[str, str]:
    if not metadata_filters:
        return {}

    normalized_filters: dict[str, str] = {}
    for field in ALLOWED_METADATA_FILTER_FIELDS:
        value = str(metadata_filters.get(field, "") or "").strip()
        if value:
            normalized_filters[field] = value

    allowed_knowledge_spaces = set(collect_knowledge_spaces())
    knowledge_space = str(normalized_filters.get("knowledge_space", "") or "").strip()
    if knowledge_space and knowledge_space not in allowed_knowledge_spaces:
        normalized_filters.pop("knowledge_space", None)

    return normalized_filters


def merge_metadata_filters(inferred_filters: dict[str, str], explicit_filters: dict[str, str] | None) -> dict[str, str]:
    merged = dict(inferred_filters)
    merged.update(explicit_filters or {})
    return merged


def collect_filter_candidates() -> dict[str, set[str]]:
    candidates: dict[str, set[str]] = {field: set() for field in ALLOWED_METADATA_FILTER_FIELDS}
    user = get_current_user(required=False)
    accessible_space_ids = list_accessible_space_ids(user) if user else []
    for document in vector_store.list_documents(accessible_space_ids=accessible_space_ids):
        for field in ALLOWED_METADATA_FILTER_FIELDS:
            value = str(document.get(field, "") or "").strip()
            if value:
                candidates[field].add(value)
    return candidates


def collect_knowledge_spaces() -> list[str]:
    user = get_current_user(required=False)
    accessible_space_ids = list_accessible_space_ids(user) if user else []
    names = {
        str(document.get("knowledge_space", "") or "").strip()
        for document in vector_store.list_documents(accessible_space_ids=accessible_space_ids)
        if str(document.get("knowledge_space", "") or "").strip()
    }
    return sorted(names)


def collect_knowledge_space_records() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    user = get_current_user(required=False)
    for item in list_knowledge_spaces(user):
        name = str(item.get("name", "") or "").strip()
        if not name:
            continue
        records.append(
            {
                "name": name,
                "tags": str(item.get("tags", "") or "").strip(),
                "description": str(item.get("description", "") or "").strip(),
            }
        )
    return records


def split_knowledge_space_segments(space: str) -> list[str]:
    normalized = normalize_text(space)
    if not normalized:
        return []
    return [segment for segment in re.split(r"[/>：:·\-]+", normalized) if segment]


def knowledge_space_overlap_score(query: str, knowledge_space: str) -> int:
    normalized_query = normalize_text(query)
    normalized_space = normalize_text(knowledge_space)
    if not normalized_query or not normalized_space:
        return 0

    score = 0
    if normalized_space in normalized_query:
        score += len(normalized_space) * 3
    for segment in split_knowledge_space_segments(knowledge_space):
        if segment and segment in normalized_query:
            score += len(segment)
    return score


def should_use_knowledge_space_llm(query: str, candidates: list[str]) -> bool:
    return any(knowledge_space_overlap_score(query, candidate) > 0 for candidate in candidates)


def expand_knowledge_space_filter_values(knowledge_space: str) -> list[str]:
    normalized = str(knowledge_space or "").strip()
    if not normalized:
        return []
    return [normalized]


def expand_metadata_filters_for_hierarchy(metadata_filters: dict[str, Any]) -> dict[str, Any]:
    expanded = dict(metadata_filters)
    knowledge_space = expanded.get("knowledge_space")
    if str(knowledge_space or "").strip():
        values = expand_knowledge_space_filter_values(str(knowledge_space))
        if values:
            expanded["knowledge_space"] = values if len(values) > 1 else values[0]
    return expanded


def infer_metadata_filters(query: str) -> dict[str, str]:
    normalized_query = normalize_metadata_value(query)
    if not normalized_query:
        return {}

    inferred: dict[str, str] = {}
    candidates = collect_filter_candidates()

    for field, values in candidates.items():
        for value in sorted(values, key=len, reverse=True):
            if normalize_metadata_value(value) in normalized_query:
                inferred[field] = value
                break

    return inferred


def rank_knowledge_space_candidates(query: str, candidates: list[str]) -> list[str]:
    def score(space: str) -> tuple[int, int, str]:
        overlap_score = knowledge_space_overlap_score(query, space)
        depth_score = len(split_knowledge_space_segments(space))
        return (-overlap_score, -depth_score, -len(space), space)

    return sorted(candidates, key=score)


def _collect_hitl_options(probe_results: list[dict], field: str) -> list[str]:
    ranked: dict[str, tuple[int, float]] = {}
    for doc in probe_results:
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


def probe_knowledge_space_candidates(query: str) -> list[str]:
    user = get_current_user(required=False)
    accessible_space_ids = list_accessible_space_ids(user) if user else []
    try:
        probe_results = vector_store.query_documents(
            query,
            n_results=get_knowledge_space_resolution_probe_limit(),
            accessible_space_ids=accessible_space_ids,
        )
    except Exception:
        probe_results = []

    candidates = _collect_hitl_options(probe_results, "knowledge_space")
    if candidates:
        return candidates
    return rank_knowledge_space_candidates(query, collect_knowledge_spaces())[:HITL_OPTION_LIMIT]


def resolve_knowledge_space_with_llm(query: str, candidates: list[str]) -> dict[str, Any] | None:
    if len(candidates) <= 1:
        return None

    raw = run_auxiliary_completion(
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
    payload = extract_json_object(raw)
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


def resolve_knowledge_space(
    query: str,
    inferred_filters: dict[str, str],
    explicit_filters: dict[str, str],
    session_id: str | None = None,
) -> dict[str, Any]:
    cache_suffix = json.dumps(explicit_filters, ensure_ascii=False, sort_keys=True)
    cache_key = build_cache_key(query, cache_suffix)
    cached_result = read_session_cache(session_id, "knowledge_space_resolution", cache_key)
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
        write_session_cache(session_id, "knowledge_space_resolution", cache_key, resolved)
        return resolved

    inferred_space = str(inferred_filters.get("knowledge_space", "") or "").strip()
    if inferred_space:
        resolved = {
            "status": KNOWLEDGE_SPACE_RESOLVED,
            "knowledge_space": inferred_space,
            "candidates": [inferred_space],
            "reason": "query_match",
        }
        write_session_cache(session_id, "knowledge_space_resolution", cache_key, resolved)
        return resolved

    knowledge_spaces = collect_knowledge_spaces()
    if not knowledge_spaces:
        resolved = {
            "status": KNOWLEDGE_SPACE_UNKNOWN,
            "knowledge_space": "",
            "candidates": [],
            "reason": "empty_knowledge_base",
        }
        write_session_cache(session_id, "knowledge_space_resolution", cache_key, resolved)
        return resolved

    if len(knowledge_spaces) == 1:
        resolved = {
            "status": KNOWLEDGE_SPACE_RESOLVED,
            "knowledge_space": knowledge_spaces[0],
            "candidates": knowledge_spaces,
            "reason": "single_knowledge_space",
        }
        write_session_cache(session_id, "knowledge_space_resolution", cache_key, resolved)
        return resolved

    llm_result = None
    if should_use_knowledge_space_llm(query, knowledge_spaces):
        llm_result = resolve_knowledge_space_with_llm(query, knowledge_spaces)
    if llm_result and llm_result.get("status") == KNOWLEDGE_SPACE_RESOLVED:
        resolved = {
            **llm_result,
            "reason": "llm_resolution",
        }
        write_session_cache(session_id, "knowledge_space_resolution", cache_key, resolved)
        return resolved

    candidate_spaces = probe_knowledge_space_candidates(query)
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
    write_session_cache(session_id, "knowledge_space_resolution", cache_key, resolved)
    return resolved


def generate_query_variants(query: str, knowledge_space: str = "", session_id: str | None = None) -> tuple[list[str], bool]:
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return [], False

    config_snapshot = build_retrieval_runtime_config_snapshot()
    cache_key = build_cache_key(
        normalized_query,
        json.dumps(
            {
                "knowledge_space": knowledge_space.strip(),
                "retrieval_query_expansion_count": config_snapshot["retrieval_query_expansion_count"],
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
    cached_variants = read_session_cache(session_id, "query_variants", cache_key)
    if isinstance(cached_variants, list) and cached_variants:
        return list(cached_variants), True

    variants = [normalized_query]
    query_expansion_limit = get_query_expansion_limit()
    if query_expansion_limit <= 0:
        write_session_cache(session_id, "query_variants", cache_key, variants)
        return variants, False

    scope_hint = f"当前知识空间：{knowledge_space}\n" if knowledge_space else ""
    raw = run_auxiliary_completion(
        "你是知识库检索改写器。只输出若干行中文问句，不要编号，不要解释。",
        (
            f"{scope_hint}"
            f"原始问题：{normalized_query}\n"
            f"请生成 {query_expansion_limit} 个与原问题语义等价、但更接近正式文档写法的中文检索问句。\n"
            "要求：\n"
            "1. 不要引入原问题中没有的新事实、新对象或新流程。\n"
            "2. 可以补充同义词、正式术语、模块名称、流程名称。\n"
            "3. 每行一个问句。"
        ),
    )

    if not raw:
        write_session_cache(session_id, "query_variants", cache_key, variants)
        return variants, False

    for line in raw.splitlines():
        candidate = re.sub(r"^[\-\d\s.、]+", "", line).strip(" \t\"'“”")
        if candidate and candidate not in variants:
            variants.append(candidate)
        if len(variants) >= query_expansion_limit + 1:
            break

    write_session_cache(session_id, "query_variants", cache_key, variants)
    return variants, False


def format_context_header(metadata: dict) -> str:
    header_parts = []
    for label, key in (("知识空间", "knowledge_space"), ("标签", "tags")):
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


def metadata_match_count(query_terms: list[str], metadata: dict) -> int:
    values = [normalize_text(str(metadata.get(field, ""))) for field in QUERY_FILTER_FIELDS]
    values.extend(
        [
            normalize_text(str(metadata.get("section_title", ""))),
            normalize_text(str(metadata.get("heading_path", ""))),
            normalize_text(str(metadata.get("source_label", ""))),
        ]
    )
    return sum(1 for term in query_terms if any(term in value for value in values if value))


def emit_retrieval_progress(progress_callback: Callable[[str], None] | None, message: str) -> None:
    if progress_callback is None:
        return

    text = str(message or "").strip()
    if text:
        progress_callback(text)
