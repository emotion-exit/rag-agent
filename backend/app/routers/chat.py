import json
import asyncio
import re
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from app.agent.rag_agent import (
    build_retrieval_progress_steps,
    build_source_payload,
    build_source_payload_with_trace,
    create_rag_agent,
)
from app.services.document_assets import get_document_image, list_document_images
from app.services.vector_store import get_document_chunk

router = APIRouter(prefix="/api/chat", tags=["chat"])

APP_NAME = "rag_agent_app"
session_service = InMemorySessionService()
GENERIC_THOUGHT_TEXT = "正在结合检索结果整理答案。"
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
)
STRUCTURED_RESPONSE_TAGS = ("analysis_summary", "final_answer")
PLACEHOLDER_ANSWER_PATTERNS = (
    r"^direct answer to the user",
    r"short and precise",
    r"source hint",
    r"直接给用户的最终答案",
    r"填写最终答案",
    r"模板句",
)


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str
    sources: list[dict] = []


class SourceDetailResponse(BaseModel):
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
    return str(value or "").strip().lower()


def _same_section(metadata: dict, image: dict) -> bool:
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
    image_paragraph = int(image.get("paragraph_index", 0) or 0)
    chunk_start = int(metadata.get("paragraph_index_start", 0) or 0)
    chunk_end = int(metadata.get("paragraph_index_end", 0) or 0)

    if image_paragraph <= 0 or chunk_start <= 0 or chunk_end <= 0:
        return False
    if not _same_section(metadata, image):
        return False

    return chunk_start - 2 <= image_paragraph <= chunk_end + 2


def _matches_pdf_image(metadata: dict, image: dict) -> bool:
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
    source_page = int(metadata.get("source_page", 0) or 0)
    related_images = []

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

        related_images.append(
            {
                "image_id": image_id,
                "filename": item.get("filename", ""),
                "source_label": item.get("source_label", ""),
                "source_page": int(item.get("source_page", 0) or 0),
                "anchor_text": item.get("anchor_text", ""),
                "url": str(request.url_for("get_document_image_file", doc_id=doc_id, image_id=image_id)),
            }
        )

    return related_images


def _sanitize_user_visible_text(text: str, *, strip_reasoning: bool = True) -> str:
    sanitized = text
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

    sanitized = re.sub(r"`[^`]+`", "知识库检索", sanitized)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    if strip_reasoning:
        filtered_lines = []
        for raw_line in sanitized.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if any(re.search(pattern, line) for pattern in INTERNAL_REASONING_LINE_PATTERNS):
                continue
            filtered_lines.append(line)

        if filtered_lines:
            sanitized = "\n".join(filtered_lines)

    return sanitized


def _extract_tag_content(text: str, tag_name: str) -> str:
    match = re.search(
        rf"<{tag_name}>\s*(.*?)\s*</{tag_name}>",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return match.group(1).strip()


def _split_structured_response(text: str) -> tuple[str, str]:
    normalized = (text or "").strip()
    if not normalized:
        return "", ""

    analysis_summary = _extract_tag_content(normalized, "analysis_summary")
    final_answer = _extract_tag_content(normalized, "final_answer")

    if analysis_summary or final_answer:
        return analysis_summary, final_answer or normalized

    return "", normalized


def _looks_like_placeholder_answer(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    if not normalized:
        return False

    return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in PLACEHOLDER_ANSWER_PATTERNS)


async def _ensure_session_exists(session_id: str) -> None:
    """Create the in-memory session when it does not exist yet."""
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
) -> AsyncIterator[str]:
    """Run the ADK agent and stream SSE events to the client."""
    agent = create_rag_agent()
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

    event_queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def produce_events() -> None:
        try:
            response_parts: list[str] = []
            async for event in runner.run_async(
                user_id="user",
                session_id=session_id,
                new_message=user_content,
            ):
                if event.content and event.content.parts:
                    event_type = "answer" if event.is_final_response() else "thought"
                    for part in event.content.parts:
                        if part.text:
                            if event_type == "thought":
                                continue

                            response_parts.append(part.text)
                if event.is_final_response():
                    break

            raw_response = "".join(response_parts).strip()
            thought_summary, final_answer = _split_structured_response(raw_response)

            if _looks_like_placeholder_answer(final_answer):
                thought_summary = ""
                final_answer = raw_response

            sanitized_thought = _sanitize_user_visible_text(
                thought_summary,
                strip_reasoning=False,
            )
            if sanitized_thought:
                await event_queue.put(
                    f"data: {json.dumps({'type': 'thought', 'content': sanitized_thought}, ensure_ascii=False)}\n\n"
                )

            await event_queue.put(
                f"data: {json.dumps({'type': 'progress', 'content': '已完成结果整理，正在输出答案。'}, ensure_ascii=False)}\n\n"
            )

            payload = _sanitize_user_visible_text(final_answer or raw_response)
            if payload:
                await event_queue.put(
                    f"data: {json.dumps({'type': 'answer', 'content': payload}, ensure_ascii=False)}\n\n"
                )

            await event_queue.put(f"data: {json.dumps({'type': 'done', 'content': ''})}\n\n")
        except Exception as exc:
            await event_queue.put(
                f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
            )
        finally:
            await event_queue.put(None)

    producer = asyncio.create_task(produce_events())

    try:
        yield (
            "data: "
            f"{json.dumps({'type': 'start', 'content': '已接收问题，正在准备检索。'}, ensure_ascii=False)}"
            "\n\n"
        )

        source_summaries, retrieval_trace = build_source_payload_with_trace(message)

        for step in build_retrieval_progress_steps(retrieval_trace):
            yield (
                "data: "
                f"{json.dumps({'type': 'progress', 'content': step}, ensure_ascii=False)}"
                "\n\n"
            )

        if source_summaries:
            yield (
                "data: "
                f"{json.dumps({'type': 'sources', 'content': '', 'sources': source_summaries}, ensure_ascii=False)}"
                "\n\n"
            )
        while True:
            event = await event_queue.get()

            if event is None:
                break

            yield event
    finally:
        if not producer.done():
            producer.cancel()
            try:
                await producer
            except asyncio.CancelledError:
                pass


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat response via Server-Sent Events."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    return StreamingResponse(
        _stream_agent_response(request.message, request.session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Non-streaming chat endpoint."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    agent = create_rag_agent()
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
        final_reply = raw_reply
    reply = _sanitize_user_visible_text(final_reply or raw_reply)
    sources, _ = build_source_payload(request.message)
    return ChatResponse(reply=reply, sources=sources)


@router.get("/sources/{doc_id}/{chunk_index}", response_model=SourceDetailResponse)
async def get_chat_source_detail(doc_id: str, chunk_index: int, request: Request):
    """Fetch a full source excerpt on demand for the chat UI."""
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
    image = get_document_image(doc_id, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    file_path, metadata = image
    return FileResponse(
        file_path,
        media_type=metadata.get("content_type", "image/png"),
        filename=metadata.get("filename") or metadata.get("stored_name") or f"{image_id}.png",
    )
