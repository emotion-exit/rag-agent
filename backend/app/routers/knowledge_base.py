import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services.document_assets import delete_document_assets, save_document_images
from app.services.document_processor import (
    SUPPORTED_DOCUMENT_EXTENSIONS,
    extract_document_chunks,
    extract_document_images,
)
from app.services.embedding_text_splitter import count_tokens, split_text_for_embedding
from app.services.vector_store import add_documents, delete_document, list_documents, collection_count

router = APIRouter(prefix="/api/knowledge-base", tags=["knowledge-base"])
logger = logging.getLogger(__name__)

# Supported MIME types and extensions
ALLOWED_EXTENSIONS = set(SUPPORTED_DOCUMENT_EXTENSIONS)
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
PDF_IMAGE_EXTRACTION_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int
    upload_time: str
    knowledge_space: str = ""
    category: str = ""
    topic: str = ""
    tags: str = ""
    version_label: str = ""
    image_count: int = 0


def _normalize_metadata_value(value: str | None) -> str:
    return (value or "").strip()


def _split_text_for_embedding(text: str) -> list[str]:
    return split_text_for_embedding(
        text,
        max_tokens=settings.embedding_max_input_tokens,
        target_tokens=settings.embedding_target_chunk_tokens,
        overlap_tokens=settings.embedding_chunk_overlap_tokens,
        tokenizer_model=settings.get_embedding_tokenizer_model(),
        tokenizer_encoding=settings.embedding_tokenizer_encoding,
    )


def _build_embedding_prefix(chunk_info: dict, metadata: dict[str, str]) -> str:
    parts = []

    for label, key in (
        ("知识空间", "knowledge_space"),
        ("分类", "category"),
        ("主题", "topic"),
        ("标签", "tags"),
        ("版本", "version_label"),
    ):
        value = str(metadata.get(key, "") or "").strip()
        if value:
            parts.append(f"[{label}] {value}")

    for label, key in (("章节路径", "heading_path"), ("章节标题", "section_title"), ("来源位置", "source_label")):
        value = str(chunk_info.get(key, "") or "").strip()
        if value:
            parts.append(f"[{label}] {value}")

    return "\n".join(parts).strip()


def _split_content_with_prefix(content: str, prefix: str) -> list[tuple[str, str]]:
    normalized_content = str(content or "").strip()
    if not normalized_content:
        return []

    prefix_text = prefix.strip()
    if not prefix_text:
        pieces = _split_text_for_embedding(normalized_content)
        return [(piece, piece) for piece in pieces]

    prefix_tokens = count_tokens(
        prefix_text,
        settings.get_embedding_tokenizer_model(),
        settings.embedding_tokenizer_encoding,
    )
    min_body_tokens = 32
    available_max_tokens = max(settings.embedding_max_input_tokens - prefix_tokens, min_body_tokens)
    available_target_tokens = min(
        max(settings.embedding_target_chunk_tokens - prefix_tokens, min_body_tokens),
        available_max_tokens,
    )
    available_overlap_tokens = min(
        settings.embedding_chunk_overlap_tokens,
        max(available_target_tokens - 1, 0),
    )

    pieces = split_text_for_embedding(
        normalized_content,
        max_tokens=available_max_tokens,
        target_tokens=available_target_tokens,
        overlap_tokens=available_overlap_tokens,
        tokenizer_model=settings.get_embedding_tokenizer_model(),
        tokenizer_encoding=settings.embedding_tokenizer_encoding,
    )

    return [
        (piece, f"{prefix_text}\n[正文]\n{piece}".strip())
        for piece in pieces
    ]


def _prepare_embedding_chunks(
    chunks_with_sources: list[dict],
    metadata: dict[str, str],
) -> list[dict]:
    normalized_chunks: list[dict] = []

    for chunk_info in chunks_with_sources:
        content = str(chunk_info.get("content", "")).strip()
        if not content:
            continue

        prefix = _build_embedding_prefix(chunk_info, metadata)
        split_contents = _split_content_with_prefix(content, prefix)
        for split_content, embedding_content in split_contents:
            normalized_chunks.append(
                {
                    **chunk_info,
                    "content": split_content,
                    "embedding_content": embedding_content,
                }
            )

    return normalized_chunks


class KnowledgeBaseStats(BaseModel):
    total_chunks: int
    total_documents: int


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    knowledge_space: str = Form(default=""),
    category: str = Form(default=""),
    topic: str = Form(default=""),
    tags: str = Form(default=""),
    version_label: str = Form(default=""),
):
    """Upload a document to the knowledge base."""
    try:
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

        doc_id = str(uuid.uuid4())
        chunks_with_sources = extract_document_chunks(file_bytes, file.filename or "")
        normalized_knowledge_space = _normalize_metadata_value(knowledge_space)
        normalized_category = _normalize_metadata_value(category)
        normalized_topic = _normalize_metadata_value(topic)
        normalized_tags = _normalize_metadata_value(tags)
        normalized_version_label = _normalize_metadata_value(version_label)
        semantic_metadata = {
            "knowledge_space": normalized_knowledge_space,
            "category": normalized_category,
            "topic": normalized_topic,
            "tags": normalized_tags,
            "version_label": normalized_version_label,
        }

        chunks_with_sources = _prepare_embedding_chunks(chunks_with_sources, semantic_metadata)
        if not chunks_with_sources:
            raise HTTPException(status_code=400, detail="Could not extract text content from file")

        chunks = [item["content"] for item in chunks_with_sources]
        embedding_contents = [item["embedding_content"] for item in chunks_with_sources]
        image_warning = ""
        if ext == ".pdf" and len(file_bytes) > PDF_IMAGE_EXTRACTION_MAX_BYTES:
            document_images = []
            image_warning = "文件较大，已跳过 PDF 图片提取以加快上传。"
        else:
            document_images = extract_document_images(file_bytes, file.filename or "")
        saved_images = save_document_images(doc_id, document_images)

        upload_time = datetime.now(timezone.utc).isoformat()

        # Store in vector DB
        metadatas = [
            {
                "doc_id": doc_id,
                "filename": file.filename or "unknown",
                "chunk_index": i,
                "upload_time": upload_time,
                "knowledge_space": normalized_knowledge_space,
                "category": normalized_category,
                "topic": normalized_topic,
                "tags": normalized_tags,
                "version_label": normalized_version_label,
                "source_type": chunk_info.get("source_type", "text"),
                "source_label": chunk_info.get("source_label", "正文文本"),
                "source_page": int(chunk_info.get("source_page", 0) or 0),
                "section_title": chunk_info.get("section_title", ""),
                "heading_path": chunk_info.get("heading_path", ""),
                "paragraph_index_start": int(chunk_info.get("paragraph_index_start", 0) or 0),
                "paragraph_index_end": int(chunk_info.get("paragraph_index_end", 0) or 0),
                "block_index_start": int(chunk_info.get("block_index_start", 0) or 0),
                "block_index_end": int(chunk_info.get("block_index_end", 0) or 0),
                "image_count": len(saved_images),
            }
            for i, chunk_info in enumerate(chunks_with_sources)
        ]

        count = add_documents(chunks, metadatas, doc_id, embedding_texts=embedding_contents)

        success_message = (
            f"成功上传 '{file.filename}'，共创建 {count} 个文本块，检测到 {len(saved_images)} 张文档图片（仅引用展示，不参与检索）"
        )
        if image_warning:
            success_message = f"{success_message}。{image_warning}"

        return {
            "success": True,
            "doc_id": doc_id,
            "filename": file.filename,
            "chunks_created": count,
            "image_count": len(saved_images),
            "message": success_message,
            "warning": image_warning,
        }
    except HTTPException:
        raise
    except ModuleNotFoundError as exc:
        missing_module = getattr(exc, "name", "") or "unknown"
        logger.exception("Document upload failed due to missing dependency: %s", missing_module)
        raise HTTPException(
            status_code=500,
            detail=f"文档解析依赖缺失：{missing_module}，请检查后端运行环境依赖是否已正确安装。",
        ) from exc
    except Exception as exc:
        logger.exception("Document upload failed for file '%s'", file.filename)
        raise HTTPException(
            status_code=500,
            detail=f"文档上传失败：{exc}",
        ) from exc


@router.get("/documents")
async def get_documents():
    """List all documents in the knowledge base."""
    docs = list_documents()
    result = []
    for doc in docs:
        result.append({
            "doc_id": doc.get("doc_id", ""),
            "filename": doc.get("filename", "未知"),
            "chunk_count": int(doc.get("chunk_count", 0) or 0),
            "upload_time": doc.get("upload_time", ""),
            "knowledge_space": doc.get("knowledge_space", ""),
            "category": doc.get("category", ""),
            "topic": doc.get("topic", ""),
            "tags": doc.get("tags", ""),
            "version_label": doc.get("version_label", ""),
            "image_count": int(doc.get("image_count", 0) or 0),
        })
    return {"documents": result, "total": len(result)}


@router.delete("/documents/{doc_id}")
async def delete_document_endpoint(doc_id: str):
    """Delete a document from the knowledge base."""
    deleted_count = delete_document(doc_id)
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    delete_document_assets(doc_id)
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
