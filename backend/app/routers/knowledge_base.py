import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services.document_processor import extract_document_chunks
from app.services.vector_store import add_documents, delete_document, list_documents, collection_count

router = APIRouter(prefix="/api/knowledge-base", tags=["knowledge-base"])

# Supported MIME types and extensions
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".rst", ".csv"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int
    upload_time: str
    system_name: str = ""
    module_name: str = ""
    feature_name: str = ""
    version_name: str = ""
    doc_type: str = ""


def _normalize_metadata_value(value: str | None) -> str:
    return (value or "").strip()


class KnowledgeBaseStats(BaseModel):
    total_chunks: int
    total_documents: int


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    system_name: str = Form(default=""),
    module_name: str = Form(default=""),
    feature_name: str = Form(default=""),
    version_name: str = Form(default=""),
    doc_type: str = Form(default=""),
):
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

    chunks_with_sources = extract_document_chunks(file_bytes, file.filename or "")
    if not chunks_with_sources:
        raise HTTPException(status_code=400, detail="Could not extract text or OCR content from file")

    chunks = [item["content"] for item in chunks_with_sources]
    ocr_chunk_count = sum(1 for item in chunks_with_sources if item.get("source_type") == "image_ocr")

    # Generate document ID
    doc_id = str(uuid.uuid4())
    upload_time = datetime.now(timezone.utc).isoformat()
    normalized_system_name = _normalize_metadata_value(system_name)
    normalized_module_name = _normalize_metadata_value(module_name)
    normalized_feature_name = _normalize_metadata_value(feature_name)
    normalized_version_name = _normalize_metadata_value(version_name)
    normalized_doc_type = _normalize_metadata_value(doc_type)

    # Store in vector DB
    metadatas = [
        {
            "doc_id": doc_id,
            "filename": file.filename or "unknown",
            "chunk_index": i,
            "upload_time": upload_time,
            "system_name": normalized_system_name,
            "module_name": normalized_module_name,
            "feature_name": normalized_feature_name,
            "version_name": normalized_version_name,
            "doc_type": normalized_doc_type,
            "source_type": chunk_info.get("source_type", "text"),
            "source_label": chunk_info.get("source_label", "正文文本"),
            "source_page": int(chunk_info.get("source_page", 0) or 0),
        }
        for i, chunk_info in enumerate(chunks_with_sources)
    ]

    count = add_documents(chunks, metadatas, doc_id)

    return {
        "success": True,
        "doc_id": doc_id,
        "filename": file.filename,
        "chunks_created": count,
        "ocr_chunks_created": ocr_chunk_count,
        "message": f"成功上传 '{file.filename}'，共创建 {count} 个文本块，其中截图 OCR {ocr_chunk_count} 个",
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
            "system_name": doc.get("system_name", ""),
            "module_name": doc.get("module_name", ""),
            "feature_name": doc.get("feature_name", ""),
            "version_name": doc.get("version_name", ""),
            "doc_type": doc.get("doc_type", ""),
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
