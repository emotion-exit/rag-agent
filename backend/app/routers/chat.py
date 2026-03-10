import json
import asyncio
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from app.agent.rag_agent import build_source_summaries, create_rag_agent

router = APIRouter(prefix="/api/chat", tags=["chat"])

APP_NAME = "rag_agent_app"
session_service = InMemorySessionService()


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str
    sources: list[dict] = []


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

    source_summaries = build_source_summaries(message)

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
    return ChatResponse(reply=reply, sources=build_source_summaries(request.message))
