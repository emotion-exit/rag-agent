import os
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services.document_processor import extract_text_from_file, chunk_text
from app.services.vector_store import add_documents, delete_document, list_documents, collection_count

router = APIRouter(prefix="/api/knowledge-base", tags=["knowledge-base"])

# Supported MIME types and extensions
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".rst", ".csv"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int
    upload_time: str


class KnowledgeBaseStats(BaseModel):
    total_chunks: int
    total_documents: int


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a document to the knowledge base."""
    # Validate file extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file content
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 20 MB)")
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    # Extract text
    text = extract_text_from_file(file_bytes, file.filename or "")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    # Chunk text
    chunks = chunk_text(text, chunk_size=500, chunk_overlap=50)
    if not chunks:
        raise HTTPException(status_code=400, detail="No text chunks could be created")

    # Generate document ID
    doc_id = str(uuid.uuid4())
    from datetime import datetime, timezone
    upload_time = datetime.now(timezone.utc).isoformat()

    # Store in vector DB
    metadatas = [
        {
            "doc_id": doc_id,
            "filename": file.filename or "unknown",
            "chunk_index": i,
            "upload_time": upload_time,
        }
        for i in range(len(chunks))
    ]

    count = add_documents(chunks, metadatas, doc_id)

    return {
        "success": True,
        "doc_id": doc_id,
        "filename": file.filename,
        "chunks_created": count,
        "message": f"成功上传 '{file.filename}'，共创建 {count} 个文本块",
    }


@router.get("/documents")
async def get_documents():
    """List all documents in the knowledge base."""
    docs = list_documents()
    result = []
    for doc in docs:
        result.append({
            "doc_id": doc.get("doc_id", ""),
            "filename": doc.get("filename", "未知"),
            "upload_time": doc.get("upload_time", ""),
        })
    return {"documents": result, "total": len(result)}


@router.delete("/documents/{doc_id}")
async def delete_document_endpoint(doc_id: str):
    """Delete a document from the knowledge base."""
    deleted_count = delete_document(doc_id)
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "success": True,
        "message": f"已删除文档（共删除 {deleted_count} 个文本块）",
    }


@router.get("/stats", response_model=KnowledgeBaseStats)
async def get_stats():
    """Get knowledge base statistics."""
    docs = list_documents()
    return KnowledgeBaseStats(
        total_chunks=collection_count(),
        total_documents=len(docs),
    )
