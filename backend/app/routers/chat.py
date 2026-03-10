import json
import asyncio
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from app.agent.rag_agent import create_rag_agent
from app.config import settings

router = APIRouter(prefix="/api/chat", tags=["chat"])

APP_NAME = "rag_agent_app"
session_service = InMemorySessionService()


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] = []


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

    # Ensure the session exists
    try:
        await session_service.get_session(app_name=APP_NAME, session_id=session_id, user_id="user")
    except Exception:
        await session_service.create_session(app_name=APP_NAME, session_id=session_id, user_id="user")

    user_content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=message)],
    )

    full_reply = []

    try:
        async for event in runner.run_async(
            user_id="user",
            session_id=session_id,
            new_message=user_content,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            full_reply.append(part.text)
                            yield f"data: {json.dumps({'type': 'text', 'content': part.text})}\n\n"
                break
            elif event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text and not event.is_final_response():
                        full_reply.append(part.text)
                        yield f"data: {json.dumps({'type': 'text', 'content': part.text})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'content': ''})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"


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

    try:
        await session_service.get_session(app_name=APP_NAME, session_id=request.session_id, user_id="user")
    except Exception:
        await session_service.create_session(app_name=APP_NAME, session_id=request.session_id, user_id="user")

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
    return ChatResponse(reply=reply)
