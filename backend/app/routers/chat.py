"""聊天路由与流式输出控制。

这份路由层做的不只是 FastAPI 的接口转发，还负责：
1. 把 ADK 事件流转成前端可消费的 SSE 事件。
2. 过滤模型泄漏出的思维链、标签和内部实现细节。
3. 在流式模式下拆分 thought / answer / progress / sources 等不同事件类型。
"""

import json
import asyncio
import re
from urllib.parse import quote
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from app.agent.rag_agent import (
    NO_KNOWLEDGE_BASE_ANSWER,
    build_hitl_clarification,
    build_retrieval_progress_steps,
    build_source_payload_with_trace,
    create_rag_agent,
)
from app.services.document_assets import get_document_image, list_document_images
from app.services.vector_store import get_document_chunk

router = APIRouter(prefix="/api/chat", tags=["chat"])

APP_NAME = "rag_agent_app"
session_service = InMemorySessionService()
# 进入真正答案输出阶段时给前端的统一状态提示。
ANSWER_STREAM_PROGRESS = "已进入答案生成，正在逐段输出内容。"
RETRIEVAL_PREPARING_PROGRESS = "正在识别知识空间并准备检索条件。"
# 这些模式用于把模型偶尔泄漏出来的内部函数名、模块名和接口路径替换掉。
INTERNAL_IDENTIFIER_PATTERNS = (
    r"\bretrieve_from_knowledge_base\b",
    r"\bbuild_source_payload\b",
    r"\bquery_documents\b",
    r"\bvector_store\b",
    r"\bapp\.[a-zA-Z0-9_\.]+\b",
    r"/api/[a-zA-Z0-9_\-/{}]+",
    r"\b[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*\b",
)
INTERNAL_REASONING_LINE_PATTERNS = (
    r"^(好的[，。,:：\s]*)?(我现在需要|我需要先|接下来我会|接下来需要|让我|我先|首先我会)",
    r"^(根据|结合)之前的(工具调用|检索结果|分析)",
    r"^为了回答.*(我会|需要)",
    r"^这里(提到|说明|显示).*(让我|我再)",
    r"^现在我需要",
    r"^(工具返回的结果|检索结果|来源)里.*(提到|显示|说明)",
    r"^(接下来|然后|最后)[，。,:：\s]*(我需要|需要|我会)",
    r"^(需要确认|根据规则|确保|看起来步骤|所以最终答案|最终答案应该|只输出最终答案|符合要求)",
    r"^用户问的是",
)
FINAL_ANSWER_CUE_PATTERNS = (
    r"(?:所以|因此|那么)?最终答案(?:应该)?[：:]",
    r"只输出最终答案[：:]",
)
STRUCTURED_RESPONSE_TAGS = ("final_answer",)
HIDDEN_REASONING_TAGS = ("think", "analysis", "analysis_summary", "reasoning")
PLACEHOLDER_ANSWER_PATTERNS = (
    r"^direct answer to the user",
    r"short and precise",
    r"source hint",
    r"直接给用户的最终答案",
    r"填写最终答案",
    r"模板句",
    r"^<final_answer>",
)
STREAM_CHUNK_MAX_LENGTH = 72
# 即使上游模型一次性吐出整段文本，也通过轻微延迟制造更自然的流式观感。
STREAM_CHUNK_DELAY_SECONDS = 0.035


class ChatRequest(BaseModel):
    """聊天请求体。"""
    message: str
    session_id: str = "default"
    retrieval_filters: dict[str, str] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """非流式聊天接口的响应体。"""
    reply: str
    sources: list[dict] = []


class SourceDetailResponse(BaseModel):
    """来源详情弹窗需要的完整片段结构。"""
    doc_id: str
    filename: str
    chunk_index: int
    excerpt: str
    source_type: str = "text"
    source_label: str = ""
    source_page: int = 0
    section_title: str = ""
    heading_path: str = ""
    image_count: int = 0
    images: list[dict] = []


def _normalize_compare_text(value: object) -> str:
    """统一比较文本格式，避免大小写和空白差异影响匹配。"""
    return str(value or "").strip().lower()


def _same_section(metadata: dict, image: dict) -> bool:
    """判断图片和正文 chunk 是否属于同一章节。"""
    chunk_heading = _normalize_compare_text(metadata.get("heading_path"))
    image_heading = _normalize_compare_text(image.get("heading_path"))
    if chunk_heading and image_heading:
        return chunk_heading == image_heading

    chunk_section = _normalize_compare_text(metadata.get("section_title"))
    image_section = _normalize_compare_text(image.get("section_title"))
    if chunk_section and image_section:
        return chunk_section == image_section

    return True


def _matches_docx_image(metadata: dict, image: dict) -> bool:
    """基于段落索引判断 docx 图片是否属于当前文本片段。"""
    image_paragraph = int(image.get("paragraph_index", 0) or 0)
    chunk_start = int(metadata.get("paragraph_index_start", 0) or 0)
    chunk_end = int(metadata.get("paragraph_index_end", 0) or 0)

    if image_paragraph <= 0 or chunk_start <= 0 or chunk_end <= 0:
        return False
    if not _same_section(metadata, image):
        return False

    return chunk_start - 2 <= image_paragraph <= chunk_end + 2


def _matches_pdf_image(metadata: dict, image: dict) -> bool:
    """基于页码和 block 索引判断 PDF 图片是否属于当前文本片段。"""
    source_page = int(metadata.get("source_page", 0) or 0)
    image_page = int(image.get("source_page", 0) or 0)
    if source_page <= 0 or image_page != source_page:
        return False
    if not _same_section(metadata, image):
        return False

    image_block = int(image.get("block_index", 0) or 0)
    chunk_start = int(metadata.get("block_index_start", 0) or 0)
    chunk_end = int(metadata.get("block_index_end", 0) or 0)
    if image_block <= 0 or chunk_start <= 0 or chunk_end <= 0:
        return False

    return chunk_start - 2 <= image_block <= chunk_end + 2


def _select_related_images(metadata: dict, request: Request, doc_id: str) -> list[dict]:
    """为来源详情挑选同页 / 同段附近的关联图片。"""
    source_page = int(metadata.get("source_page", 0) or 0)
    related_images = []
    public_config = request.headers.get("x-rag-public-config", "").strip()

    for item in list_document_images(doc_id):
        image_id = str(item.get("image_id", "")).strip()
        if not image_id:
            continue

        if source_page > 0:
            is_related = _matches_pdf_image(metadata, item)
        else:
            is_related = _matches_docx_image(metadata, item)

        if not is_related:
            continue

        image_url = str(request.url_for("get_document_image_file", doc_id=doc_id, image_id=image_id))
        if public_config:
            image_url = f"{image_url}?public_config={quote(public_config, safe='')}"

        related_images.append(
            {
                "image_id": image_id,
                "filename": item.get("filename", ""),
                "source_label": item.get("source_label", ""),
                "source_page": int(item.get("source_page", 0) or 0),
                "anchor_text": item.get("anchor_text", ""),
                "url": image_url,
            }
        )

    return related_images


def _sanitize_user_visible_text(text: str, *, strip_reasoning: bool = True) -> str:
    """把模型原始输出清洗成可展示文本。

    这里同时处理几类问题：
    - 去掉内部函数名、接口路径、XML 风格标签。
    - 去掉 Markdown 代码围栏，避免模型把伪结构化输出原样暴露给用户。
    - 按需剔除“我需要先分析”“根据工具结果”这类思维链句子。
    """
    sanitized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    replacements = {
        "retrieve_from_knowledge_base": "知识库检索",
        "build_source_payload": "来源整理",
        "query_documents": "检索过程",
        "vector_store": "知识库",
    }

    for old, new in replacements.items():
        sanitized = sanitized.replace(old, new)

    for pattern in INTERNAL_IDENTIFIER_PATTERNS:
        sanitized = re.sub(pattern, "知识库检索", sanitized)

    sanitized = _strip_hidden_reasoning_blocks(sanitized)
    sanitized = re.sub(r"```[\s\S]*?```", "", sanitized)
    sanitized = re.sub(r"`([^`]+)`", r"\1", sanitized)

    filtered_lines = []
    pending_blank_line = False
    for raw_line in sanitized.splitlines():
        line = raw_line.strip()

        if not line:
            pending_blank_line = bool(filtered_lines)
            continue

        if strip_reasoning and any(re.search(pattern, line) for pattern in INTERNAL_REASONING_LINE_PATTERNS):
            continue

        if pending_blank_line and filtered_lines:
            filtered_lines.append("")
            pending_blank_line = False

        filtered_lines.append(line)

    sanitized = "\n".join(filtered_lines).strip()

    return sanitized


def _strip_hidden_reasoning_blocks(text: str) -> str:
    """删除 think / analysis 等隐藏推理块。"""
    stripped = text or ""

    for tag in HIDDEN_REASONING_TAGS:
        stripped = re.sub(
            rf"<{tag}>[\s\S]*?</{tag}>",
            "",
            stripped,
            flags=re.IGNORECASE,
        )
        stripped = re.sub(rf"</?{tag}>", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(rf"{tag}>", "", stripped, flags=re.IGNORECASE)

    return stripped


def _strip_structured_tags(text: str) -> str:
    """删除最终答案标签等结构化包裹。"""
    stripped = _strip_hidden_reasoning_blocks(text or "")
    for tag in STRUCTURED_RESPONSE_TAGS:
        stripped = re.sub(rf"</?{tag}>", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(rf"{tag}>", "", stripped, flags=re.IGNORECASE)
    return stripped.strip()


def _extract_tag_content(text: str, tag_name: str) -> str:
    """提取完整闭合标签中的内容。"""
    match = re.search(
        rf"<?{tag_name}>\s*(.*?)\s*</{tag_name}>",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return match.group(1).strip()


def _extract_partial_tag_content(text: str, tag_name: str) -> tuple[str, bool, bool]:
    """提取流式场景下可能尚未闭合的标签内容。"""
    match = re.search(rf"<?{tag_name}>", text, flags=re.IGNORECASE)
    if not match:
        return "", False, False

    content_start = match.end()
    end_match = re.search(rf"</{tag_name}>", text[content_start:], flags=re.IGNORECASE)
    if end_match:
        content = text[content_start : content_start + end_match.start()].strip()
        return content, True, True

    return text[content_start:].lstrip(), True, False


def _split_structured_response(text: str) -> tuple[str, str]:
    """从模型原始响应中提取最终答案。

    当前主要返回 final_answer；第一个返回值预留给未来需要恢复结构化 thought 时使用。
    """
    normalized = (text or "").strip()
    if not normalized:
        return "", ""

    final_answer = _extract_tag_content(normalized, "final_answer")

    if not final_answer:
        final_answer, final_started, _ = _extract_partial_tag_content(normalized, "final_answer")
        if not final_started:
            final_answer = ""

    if final_answer:
        return "", _strip_structured_tags(final_answer)

    return "", _extract_visible_answer_text(normalized)


def _is_reasoning_line(line: str) -> bool:
    """判断单行文本是否更像思维链，而不是用户应该看到的最终回答。"""
    return any(re.search(pattern, line) for pattern in INTERNAL_REASONING_LINE_PATTERNS)


def _looks_like_answer_start(line: str) -> bool:
    """判断一行是否像正式答案的起始。

    目前优先识别三类常见答案开头：
    - 有序列表
    - 无序列表
    - 来源说明
    """
    return bool(
        re.match(r"^\d+\.\s+", line)
        or re.match(r"^[-*]\s+", line)
        or re.match(r"^来源[：:]", line)
    )


def _extract_answer_after_cue(text: str) -> str:
    """如果模型写了“最终答案：”之类提示语，只截取其后正文。"""
    normalized = text or ""
    for pattern in FINAL_ANSWER_CUE_PATTERNS:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            continue

        candidate = normalized[match.end() :].strip()
        if candidate:
            return candidate

    return normalized.strip()


def _extract_visible_answer_text(text: str) -> str:
    """提取并清洗用户最终可见的答案正文。"""
    candidate = _extract_answer_after_cue(_strip_structured_tags(text))
    return _sanitize_user_visible_text(candidate, strip_reasoning=True)


def _split_visible_stream_sections(text: str) -> tuple[str, str]:
    """把流式增量文本拆成 thought 和 answer 两部分。

    这一步是当前流式体验的关键：
    - 如果模型显式输出“最终答案：”，就以前面为 thought、后面为 answer。
    - 如果没有显式标记，但前半段明显像思维链，后半段像列表答案，也尽量做启发式拆分。
    """
    normalized = _strip_structured_tags(text or "").strip()
    if not normalized:
        return "", ""

    final_answer = _extract_tag_content(normalized, "final_answer")
    if final_answer:
        return "", _sanitize_user_visible_text(final_answer, strip_reasoning=True)

    for pattern in FINAL_ANSWER_CUE_PATTERNS:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            continue

        thought = _sanitize_user_visible_text(normalized[: match.start()], strip_reasoning=False)
        answer = _sanitize_user_visible_text(normalized[match.end() :], strip_reasoning=True)
        return thought, answer

    lines = normalized.splitlines()
    has_reasoning = any(_is_reasoning_line(line.strip()) for line in lines if line.strip())
    if not has_reasoning:
        return "", _sanitize_user_visible_text(normalized, strip_reasoning=True)

    answer_start_index = -1
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if _looks_like_answer_start(line):
            answer_start_index = index
            break

    if answer_start_index >= 0:
        thought = _sanitize_user_visible_text(
            "\n".join(lines[:answer_start_index]),
            strip_reasoning=False,
        )
        answer = _sanitize_user_visible_text(
            "\n".join(lines[answer_start_index:]),
            strip_reasoning=True,
        )
        return thought, answer

    return _sanitize_user_visible_text(normalized, strip_reasoning=False), ""


def _looks_like_placeholder_answer(text: str) -> bool:
    """识别模型输出的占位模板，而非真实答案。"""
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    if not normalized:
        return False

    return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in PLACEHOLDER_ANSWER_PATTERNS)


def _merge_stream_text(current_text: str, incoming_text: str) -> str:
    """合并流式增量文本，尽量避免重复片段。"""
    if not incoming_text:
        return current_text
    if not current_text:
        return incoming_text
    if incoming_text == current_text or incoming_text in current_text:
        return current_text
    if incoming_text.startswith(current_text):
        return incoming_text
    if current_text.endswith(incoming_text):
        return current_text

    overlap = min(len(current_text), len(incoming_text))
    for size in range(overlap, 0, -1):
        if current_text.endswith(incoming_text[:size]):
            return current_text + incoming_text[size:]

    return current_text + incoming_text


def _split_stream_chunks(text: str, max_length: int = STREAM_CHUNK_MAX_LENGTH) -> list[str]:
    """把较长文本切成适合前端逐段展示的小块。"""
    normalized = text or ""
    if not normalized:
        return []

    chunks: list[str] = []
    cursor = 0
    preferred_breaks = ("\n", "。", "！", "？", "；", "：", "，", " ")

    while cursor < len(normalized):
        remaining = normalized[cursor:]
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        window = remaining[:max_length]
        split_at = -1
        for marker in preferred_breaks:
            split_at = max(split_at, window.rfind(marker))

        if split_at < max_length // 3:
            split_at = max_length
        else:
            split_at += 1

        chunks.append(remaining[:split_at])
        cursor += split_at

    return [chunk for chunk in chunks if chunk]


async def _ensure_session_exists(session_id: str) -> None:
    """确保 ADK 会话存在。

    当前使用 InMemorySessionService，所以服务重启后会话会丢失；
    这里每次请求前都兜底创建一次。
    """
    session = await session_service.get_session(
        app_name=APP_NAME,
        session_id=session_id,
        user_id="user",
    )
    if session is None:
        await session_service.create_session(
            app_name=APP_NAME,
            session_id=session_id,
            user_id="user",
        )


async def _stream_agent_response(
    message: str,
    session_id: str,
    retrieval_filters: dict[str, str] | None = None,
) -> AsyncIterator[str]:
    """运行 Agent，并把结果转成前端可消费的 SSE 事件流。"""
    # producer 在后台消费 ADK 事件；主协程则不断从 event_queue 取出并 yield 给浏览器。
    event_queue: asyncio.Queue[str | None] = asyncio.Queue()
    producer: asyncio.Task[None] | None = None

    async def produce_events() -> None:
        """后台生产 thought / answer / done / error 等 SSE 事件。"""
        try:
            raw_response = ""
            answer_progress_emitted = False
            sources_emitted = False
            emitted_thought_text = ""
            emitted_answer_text = ""

            async def emit_sources_if_needed() -> None:
                nonlocal sources_emitted

                if sources_emitted or not source_summaries:
                    return

                await event_queue.put(
                    f"data: {json.dumps({'type': 'sources', 'content': '', 'sources': source_summaries}, ensure_ascii=False)}\n\n"
                )
                sources_emitted = True

            async def emit_thought_chunks(thought_text: str) -> None:
                """增量发出 thought 事件，只推送尚未发过的新增部分。"""
                nonlocal emitted_thought_text

                visible_thought = _sanitize_user_visible_text(thought_text, strip_reasoning=False)
                if not visible_thought:
                    return

                if visible_thought.startswith(emitted_thought_text):
                    delta = visible_thought[len(emitted_thought_text):]
                else:
                    delta = visible_thought

                if not delta:
                    return

                emitted_thought_text = visible_thought
                for chunk in _split_stream_chunks(delta):
                    await event_queue.put(
                        f"data: {json.dumps({'type': 'thought', 'content': chunk}, ensure_ascii=False)}\n\n"
                    )
                    await asyncio.sleep(STREAM_CHUNK_DELAY_SECONDS)

            async def emit_answer_chunks(answer_text: str) -> None:
                """增量发出 answer 事件，并在第一次真正输出答案时补一个 progress。"""
                nonlocal answer_progress_emitted, emitted_answer_text

                visible_answer = _sanitize_user_visible_text(
                    _extract_answer_after_cue(_strip_structured_tags(answer_text)),
                    strip_reasoning=True,
                )
                if not visible_answer:
                    return

                if visible_answer.startswith(emitted_answer_text):
                    delta = visible_answer[len(emitted_answer_text):]
                else:
                    delta = visible_answer

                if not delta:
                    return

                if not answer_progress_emitted:
                    await event_queue.put(
                        f"data: {json.dumps({'type': 'progress', 'content': ANSWER_STREAM_PROGRESS}, ensure_ascii=False)}\n\n"
                    )
                    answer_progress_emitted = True

                emitted_answer_text = visible_answer
                answer_chunks = _split_stream_chunks(delta)
                for index, chunk in enumerate(answer_chunks):
                    await event_queue.put(
                        f"data: {json.dumps({'type': 'answer', 'content': chunk}, ensure_ascii=False)}\n\n"
                    )
                    if index == 0:
                        await emit_sources_if_needed()
                    await asyncio.sleep(STREAM_CHUNK_DELAY_SECONDS)

            async for event in runner.run_async(
                user_id="user",
                session_id=session_id,
                new_message=user_content,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            # ADK 在不同模型下可能返回完整累积文本，也可能返回增量片段；
                            # 这里统一合并为一份 raw_response，再从中拆 thought / answer。
                            raw_response = _merge_stream_text(raw_response, part.text)

                            thought_content, streamed_answer = _split_visible_stream_sections(raw_response)
                            await emit_thought_chunks(thought_content)
                            await emit_answer_chunks(streamed_answer)

                            answer_content, answer_started, _ = _extract_partial_tag_content(
                                raw_response,
                                "final_answer",
                            )
                            if answer_started:
                                await emit_answer_chunks(answer_content)

                if event.is_final_response():
                    break

            # 最终再对整段输出做一次收尾，防止中途启发式拆分漏掉末尾内容。
            raw_response = raw_response.strip()
            final_thought, final_answer_candidate = _split_visible_stream_sections(raw_response)
            await emit_thought_chunks(final_thought)
            _, final_answer = _split_structured_response(raw_response)
            final_answer = final_answer or final_answer_candidate

            if _looks_like_placeholder_answer(final_answer):
                final_answer = _extract_visible_answer_text(raw_response)

            await emit_answer_chunks(final_answer or raw_response)
            await emit_sources_if_needed()

            await event_queue.put(f"data: {json.dumps({'type': 'done', 'content': ''})}\n\n")
        except Exception as exc:
            await event_queue.put(
                f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
            )
        finally:
            await event_queue.put(None)

    try:
        # 先向前端报告请求已进入检索阶段，让界面立即有反馈。
        yield (
            "data: "
            f"{json.dumps({'type': 'start', 'content': '已接收问题，正在准备检索。'}, ensure_ascii=False)}"
            "\n\n"
        )
        yield (
            "data: "
            f"{json.dumps({'type': 'progress', 'content': RETRIEVAL_PREPARING_PROGRESS}, ensure_ascii=False)}"
            "\n\n"
        )

        # 先完成检索并判断是否需要用户进一步澄清，再决定是否继续生成答案。
        source_summaries, retrieval_trace = build_source_payload_with_trace(
            message,
            explicit_metadata_filters=retrieval_filters,
            session_id=session_id,
        )

        knowledge_space_resolution = retrieval_trace.get("knowledge_space_resolution", {}) or {}
        metadata_filters = retrieval_trace.get("metadata_filters", {}) or {}
        scope_label = str(
            knowledge_space_resolution.get("knowledge_space")
            or metadata_filters.get("knowledge_space")
            or ""
        ).strip()
        if scope_label:
            yield (
                "data: "
                f"{json.dumps({'type': 'scope', 'content': scope_label}, ensure_ascii=False)}"
                "\n\n"
            )

        clarification = build_hitl_clarification(retrieval_trace)
        if clarification:
            yield (
                "data: "
                f"{json.dumps({'type': 'clarify', 'content': clarification['question'], 'options': clarification['options']}, ensure_ascii=False)}"
                "\n\n"
            )
            yield f"data: {json.dumps({'type': 'done', 'content': ''})}\n\n"
            return

        query_variants = [
            str(item or "").strip()
            for item in retrieval_trace.get("query_variants", [])
            if str(item or "").strip()
        ]
        if query_variants:
            yield (
                "data: "
                f"{json.dumps({'type': 'retrieval_meta', 'content': '', 'query_variants': query_variants}, ensure_ascii=False)}"
                "\n\n"
            )

        for step in build_retrieval_progress_steps(retrieval_trace):
            yield (
                "data: "
                f"{json.dumps({'type': 'progress', 'content': step}, ensure_ascii=False)}"
                "\n\n"
            )

        if int(retrieval_trace.get("final_hit_count", 0) or 0) <= 0:
            yield (
                "data: "
                f"{json.dumps({'type': 'progress', 'content': '未找到可用知识库内容，停止生成答案。'}, ensure_ascii=False)}"
                "\n\n"
            )
            yield (
                "data: "
                f"{json.dumps({'type': 'answer', 'content': NO_KNOWLEDGE_BASE_ANSWER}, ensure_ascii=False)}"
                "\n\n"
            )
            yield f"data: {json.dumps({'type': 'done', 'content': ''})}\n\n"
            return

        agent = create_rag_agent(
            retrieval_filters,
            session_id=session_id,
            original_query=message,
            retrieval_documents=list(retrieval_trace.get("documents", [])),
        )
        runner = Runner(
            agent=agent,
            app_name=APP_NAME,
            session_service=session_service,
        )

        await _ensure_session_exists(session_id)

        user_content = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=message)],
        )

        # 检索阶段信息发完后，再启动真正的模型回答流，避免 answer 事件积压后一起冲出来。
        producer = asyncio.create_task(produce_events())

        while True:
            event = await event_queue.get()

            if event is None:
                break

            yield event
    finally:
        if producer is not None and not producer.done():
            producer.cancel()
            try:
                await producer
            except asyncio.CancelledError:
                pass


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """流式聊天接口。"""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    return StreamingResponse(
        _stream_agent_response(
            request.message,
            request.session_id,
            request.retrieval_filters,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """非流式聊天接口。"""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    source_summaries, retrieval_trace = build_source_payload_with_trace(
        request.message,
        explicit_metadata_filters=request.retrieval_filters,
        session_id=request.session_id,
    )
    clarification = build_hitl_clarification(retrieval_trace)
    if clarification:
        return ChatResponse(reply=clarification["question"], sources=[])

    if int(retrieval_trace.get("final_hit_count", 0) or 0) <= 0:
        return ChatResponse(reply=NO_KNOWLEDGE_BASE_ANSWER, sources=[])

    agent = create_rag_agent(
        request.retrieval_filters,
        session_id=request.session_id,
        original_query=request.message,
        retrieval_documents=list(retrieval_trace.get("documents", [])),
    )
    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    await _ensure_session_exists(request.session_id)

    user_content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=request.message)],
    )

    # 非流式模式下只取最终响应，再走和流式同一套清洗逻辑，保证表现一致。
    reply_parts = []
    async for event in runner.run_async(
        user_id="user",
        session_id=request.session_id,
        new_message=user_content,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    reply_parts.append(part.text)
            break

    raw_reply = "".join(reply_parts)
    _, final_reply = _split_structured_response(raw_reply)
    if _looks_like_placeholder_answer(final_reply):
        final_reply = _extract_visible_answer_text(raw_reply)
    reply = final_reply or _extract_visible_answer_text(raw_reply)
    return ChatResponse(reply=reply, sources=source_summaries)


@router.get("/sources/{doc_id}/{chunk_index}", response_model=SourceDetailResponse)
async def get_chat_source_detail(doc_id: str, chunk_index: int, request: Request):
    """按需返回某个来源的完整片段，用于前端来源弹窗。"""
    chunk = get_document_chunk(doc_id, chunk_index)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Source chunk not found")

    metadata = chunk.get("metadata", {})
    source_page = int(metadata.get("source_page", 0) or 0)
    images = _select_related_images(metadata, request, doc_id)

    return SourceDetailResponse(
        doc_id=doc_id,
        filename=metadata.get("filename", "未知文档"),
        chunk_index=chunk_index,
        excerpt=chunk.get("content", ""),
        source_type=metadata.get("source_type", "text"),
        source_label=metadata.get("source_label", ""),
        source_page=source_page,
        section_title=metadata.get("section_title", ""),
        heading_path=metadata.get("heading_path", ""),
        image_count=len(images),
        images=images,
    )


@router.get("/documents/{doc_id}/images/{image_id}", name="get_document_image_file")
async def get_document_image_file(doc_id: str, image_id: str):
    """返回来源关联图片文件。"""
    image = get_document_image(doc_id, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    file_path, metadata = image
    return FileResponse(
        file_path,
        media_type=metadata.get("content_type", "image/png"),
        filename=metadata.get("filename") or metadata.get("stored_name") or f"{image_id}.png",
    )
