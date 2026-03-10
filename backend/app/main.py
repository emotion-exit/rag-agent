import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import chat_router, knowledge_base_router

# Ensure data directories exist
os.makedirs(settings.chroma_persist_dir, exist_ok=True)
os.makedirs(settings.upload_dir, exist_ok=True)

app = FastAPI(
    title="RAG Agent API",
    description="Knowledge base Q&A agent powered by ADK, SiliconFlow, and OpenRouter",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(chat_router)
app.include_router(knowledge_base_router)


@app.get("/")
async def root():
    return {"message": "RAG Agent API is running", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok"}
