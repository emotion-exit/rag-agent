import json
import asyncio
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from app.agent.rag_agent import build_source_payload, create_rag_agent, _build_rerank_status
from app.services.vector_store import get_document_chunk

router = APIRouter(prefix="/api/chat", tags=["chat"])

APP_NAME = "rag_agent_app"
session_service = InMemorySessionService()


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

    source_summaries, rerank_mode = build_source_payload(message)

    user_content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=message)],
    )

    event_queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def produce_events() -> None:
        try:
            async for event in runner.run_async(
                user_id="user",
                session_id=session_id,
                new_message=user_content,
            ):
                if event.content and event.content.parts:
                    event_type = "answer" if event.is_final_response() else "thought"
                    for part in event.content.parts:
                        if part.text:
                            await event_queue.put(
                                f"data: {json.dumps({'type': event_type, 'content': part.text})}\n\n"
                            )
                if event.is_final_response():
                    break
            await event_queue.put(f"data: {json.dumps({'type': 'done', 'content': ''})}\n\n")
        except Exception as exc:
            await event_queue.put(
                f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
            )
        finally:
            await event_queue.put(None)

    producer = asyncio.create_task(produce_events())

    try:
        yield f"data: {json.dumps({'type': 'start', 'content': ''})}\n\n"
        yield (
            "data: "
            f"{json.dumps({'type': 'retrieval', 'content': _build_rerank_status(rerank_mode)}, ensure_ascii=False)}"
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

    reply = "".join(reply_parts)
    sources, _ = build_source_payload(request.message)
    return ChatResponse(reply=reply, sources=sources)


@router.get("/sources/{doc_id}/{chunk_index}", response_model=SourceDetailResponse)
async def get_chat_source_detail(doc_id: str, chunk_index: int):
    """Fetch a full source excerpt on demand for the chat UI."""
    chunk = get_document_chunk(doc_id, chunk_index)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Source chunk not found")

    metadata = chunk.get("metadata", {})
    return SourceDetailResponse(
        doc_id=doc_id,
        filename=metadata.get("filename", "未知文档"),
        chunk_index=chunk_index,
        excerpt=chunk.get("content", ""),
        source_type=metadata.get("source_type", "text"),
        source_label=metadata.get("source_label", ""),
        source_page=int(metadata.get("source_page", 0) or 0),
    )
