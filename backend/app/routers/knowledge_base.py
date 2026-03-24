import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services.document_assets import delete_document_assets, save_document_images
from app.services.knowledge_base_jobs import (
    advance_job,
    complete_job,
    create_job,
    fail_job,
    get_job,
    update_job,
)
from app.services.knowledge_spaces import (
    create_knowledge_space,
    delete_knowledge_space,
    get_knowledge_space,
    list_knowledge_spaces,
    update_knowledge_space,
)
from app.services.document_processor import (
    SUPPORTED_DOCUMENT_EXTENSIONS,
    extract_document_chunks,
    extract_document_images,
)
from app.services.embedding_text_splitter import count_tokens, split_text_for_embedding
from app.services.vector_store import (
    add_documents,
    delete_document,
    list_documents,
    collection_count,
)

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
    tags: str = ""
    image_count: int = 0
    space_id: str = ""


class KnowledgeSpaceCreateRequest(BaseModel):
    name: str
    tags: str = ""
    description: str = ""


class KnowledgeBaseJobCreatedResponse(BaseModel):
    job_id: str
    status: str
    message: str


def _normalize_metadata_value(value: str | None) -> str:
    return (value or "").strip()


def _require_metadata_value(field_label: str, value: str) -> str:
    normalized_value = _normalize_metadata_value(value)
    if not normalized_value:
        raise HTTPException(status_code=400, detail=f"{field_label}不能为空")
    return normalized_value


def _split_tag_values(value: str | None) -> list[str]:
    raw_value = _normalize_metadata_value(value)
    if not raw_value:
        return []

    parts = []
    seen: set[str] = set()
    for item in raw_value.replace("、", ",").replace("，", ",").split(","):
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        parts.append(normalized)
    return parts


def _merge_tag_values(*values: str) -> str:
    merged: list[str] = []
    seen: set[str] = set()

    for value in values:
        for item in _split_tag_values(value):
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)

    return ",".join(merged)


def _build_space_list(flat_spaces: list[dict], documents: list[dict]) -> list[dict]:
    document_counts: dict[str, int] = {}
    for doc in documents:
        space_id = _normalize_metadata_value(doc.get("space_id"))
        if not space_id:
            continue
        document_counts[space_id] = document_counts.get(space_id, 0) + 1

    spaces: list[dict] = []
    for item in flat_spaces:
        spaces.append(
            {
                **item,
                "document_count": document_counts.get(item["space_id"], 0),
            }
        )

    return sorted(spaces, key=lambda item: (str(item.get("name", "")), str(item.get("created_at", ""))))


@router.get("/spaces")
async def get_spaces():
    docs = list_documents()
    flat_spaces = list_knowledge_spaces()
    spaces = _build_space_list(flat_spaces, docs)

    return {
        "spaces": spaces,
        "summary": {
            "total_spaces": len(spaces),
            "total_documents": len(docs),
            "ungrouped_documents": 0,
        },
    }


@router.post("/spaces")
async def create_space(payload: KnowledgeSpaceCreateRequest):
    try:
        space = create_knowledge_space(
            name=payload.name,
            tags=payload.tags,
            description=payload.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "success": True,
        "space": space,
        "message": f"知识库“{space['name']}”已创建",
    }


@router.put("/spaces/{space_id}")
async def update_space(space_id: str, payload: KnowledgeSpaceCreateRequest):
    try:
        space = update_knowledge_space(
            space_id=space_id,
            name=payload.name,
            tags=payload.tags,
            description=payload.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "success": True,
        "space": space,
        "message": f"知识库“{space['name']}”已更新",
    }


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
        ("标签", "tags"),
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


def _build_document_chunk_metadatas(
    *,
    doc_id: str,
    filename: str,
    upload_time: str,
    space_id: str,
    semantic_metadata: dict[str, str],
    image_count: int,
    chunks_with_sources: list[dict],
) -> list[dict]:
    return [
        {
            "doc_id": doc_id,
            "filename": filename,
            "chunk_index": index,
            "upload_time": upload_time,
            "knowledge_space": semantic_metadata["knowledge_space"],
            "tags": semantic_metadata["tags"],
            "space_id": space_id,
            "source_type": chunk_info.get("source_type", "text"),
            "source_label": chunk_info.get("source_label", "正文文本"),
            "source_page": int(chunk_info.get("source_page", 0) or 0),
            "section_title": chunk_info.get("section_title", ""),
            "heading_path": chunk_info.get("heading_path", ""),
            "paragraph_index_start": int(chunk_info.get("paragraph_index_start", 0) or 0),
            "paragraph_index_end": int(chunk_info.get("paragraph_index_end", 0) or 0),
            "block_index_start": int(chunk_info.get("block_index_start", 0) or 0),
            "block_index_end": int(chunk_info.get("block_index_end", 0) or 0),
            "image_count": image_count,
        }
        for index, chunk_info in enumerate(chunks_with_sources)
    ]


def _resolve_semantic_metadata(
    *,
    space_id: str,
    tags: str,
) -> tuple[dict[str, str], str]:
    normalized_space_id = _normalize_metadata_value(space_id)
    if not normalized_space_id:
        raise HTTPException(status_code=400, detail="请先选择知识库")

    space = get_knowledge_space(normalized_space_id)
    if space is None:
        raise HTTPException(status_code=404, detail="知识库不存在，请先创建后再上传文档")

    normalized_knowledge_space = _require_metadata_value("知识库", str(space.get("name", "")))
    normalized_tags = _merge_tag_values(str(space.get("tags", "")), tags)

    return (
        {
            "knowledge_space": normalized_knowledge_space,
            "tags": normalized_tags,
        },
        normalized_space_id,
    )


def _store_uploaded_document(
    *,
    file_bytes: bytes,
    filename: str,
    space_id: str,
    tags: str = "",
) -> dict:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 20 MB)")
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    doc_id = str(uuid.uuid4())
    chunks_with_sources = extract_document_chunks(file_bytes, filename)
    semantic_metadata, normalized_space_id = _resolve_semantic_metadata(
        space_id=space_id,
        tags=tags,
    )

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
        document_images = extract_document_images(file_bytes, filename)
    saved_images = save_document_images(doc_id, document_images)

    upload_time = datetime.now(timezone.utc).isoformat()
    metadatas = _build_document_chunk_metadatas(
        doc_id=doc_id,
        filename=filename or "unknown",
        upload_time=upload_time,
        space_id=normalized_space_id,
        semantic_metadata=semantic_metadata,
        image_count=len(saved_images),
        chunks_with_sources=chunks_with_sources,
    )
    count = add_documents(chunks, metadatas, doc_id, embedding_texts=embedding_contents)

    success_message = (
        f"成功上传 '{filename}'，共创建 {count} 个文本块，检测到 {len(saved_images)} 张文档图片（仅引用展示，不参与检索）"
    )
    if semantic_metadata["knowledge_space"]:
        success_message = f"{success_message}，已归入“{semantic_metadata['knowledge_space']}”。"
    if image_warning:
        success_message = f"{success_message}。{image_warning}"

    return {
        "success": True,
        "doc_id": doc_id,
        "filename": filename,
        "chunks_created": count,
        "image_count": len(saved_images),
        "message": success_message,
        "warning": image_warning,
        "space_id": normalized_space_id,
    }


def _run_upload_job(
    *,
    job_id: str,
    files_payload: list[dict],
    space_id: str,
    tags: str,
) -> None:
    update_job(job_id, status="running", message="上传任务已开始。")
    uploaded_documents = 0
    uploaded_chunks = 0

    try:
        for file_payload in files_payload:
            filename = file_payload["filename"]
            update_job(
                job_id,
                current_document=filename,
                message=f"正在处理：{filename}",
            )
            result = _store_uploaded_document(
                file_bytes=file_payload["file_bytes"],
                filename=filename,
                space_id=space_id,
                tags=tags,
            )
            uploaded_documents += 1
            uploaded_chunks += int(result.get("chunks_created", 0) or 0)
            advance_job(
                job_id,
                documents=1,
                chunks=int(result.get("chunks_created", 0) or 0),
                total_chunks_delta=int(result.get("chunks_created", 0) or 0),
                message=f"已完成 {uploaded_documents}/{len(files_payload)} 个文件",
                current_document=filename,
            )

        complete_job(
            job_id,
            message=f"上传完成，已处理 {uploaded_documents} 个文件，创建 {uploaded_chunks} 个文本块。",
            result={"space_id": _normalize_metadata_value(space_id)},
        )
    except Exception as exc:
        logger.exception("Upload background job failed")
        fail_job(job_id, error_message=str(exc))


class KnowledgeBaseStats(BaseModel):
    total_chunks: int
    total_documents: int


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    space_id: str = Form(default=""),
    tags: str = Form(default=""),
):
    """Upload a document to the knowledge base."""
    try:
        file_bytes = await file.read()
        return _store_uploaded_document(
            file_bytes=file_bytes,
            filename=file.filename or "unknown",
            space_id=space_id,
            tags=tags,
        )
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


@router.post("/upload-jobs", response_model=KnowledgeBaseJobCreatedResponse)
async def create_upload_job(
    files: list[UploadFile] = File(...),
    space_id: str = Form(default=""),
    tags: str = Form(default=""),
):
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")

    normalized_space_id = _normalize_metadata_value(space_id)
    if not normalized_space_id:
        raise HTTPException(status_code=400, detail="请先选择知识库")

    files_payload: list[dict] = []
    for file in files:
        filename = file.filename or "unknown"
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            )
        file_bytes = await file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"文件 {filename} 超过 20 MB 限制")
        if len(file_bytes) == 0:
            raise HTTPException(status_code=400, detail=f"文件 {filename} 为空")
        files_payload.append({"filename": filename, "file_bytes": file_bytes})

    job = create_job(
        job_type="upload",
        total_documents=len(files_payload),
        message="上传任务已创建，等待后台处理。",
    )
    asyncio.create_task(
        asyncio.to_thread(
            _run_upload_job,
            job_id=job["job_id"],
            files_payload=files_payload,
            space_id=normalized_space_id,
            tags=tags,
        )
    )
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "message": job["message"],
    }
@router.get("/jobs/{job_id}")
async def get_knowledge_base_job(job_id: str):
    snapshot = get_job(job_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return snapshot


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
            "tags": doc.get("tags", ""),
            "image_count": int(doc.get("image_count", 0) or 0),
            "space_id": doc.get("space_id", ""),
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


async def _delete_space_and_related_data(space_id: str):
    """Delete a knowledge space and all descendant spaces/documents."""
    normalized_space_id = _normalize_metadata_value(space_id)
    if not normalized_space_id:
        raise HTTPException(status_code=404, detail="知识空间不存在")

    target_space = get_knowledge_space(normalized_space_id)
    if target_space is None:
        raise HTTPException(status_code=404, detail="知识空间不存在")

    docs = list_documents()

    try:
        deleted_space_ids = delete_knowledge_space(normalized_space_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    deleted_doc_ids: list[str] = []
    deleted_chunk_count = 0

    for doc in docs:
        doc_space_id = _normalize_metadata_value(str(doc.get("space_id", "")))
        if doc_space_id not in deleted_space_ids:
            continue

        doc_id = _normalize_metadata_value(str(doc.get("doc_id", "")))
        if not doc_id:
            continue

        deleted_chunk_count += delete_document(doc_id)
        delete_document_assets(doc_id)
        deleted_doc_ids.append(doc_id)

    return {
        "success": True,
        "message": f"知识库“{target_space['name']}”及其关联数据已删除",
        "deleted_spaces": len(deleted_space_ids),
        "deleted_documents": len(deleted_doc_ids),
        "deleted_chunks": deleted_chunk_count,
    }


@router.delete("/spaces/{space_id}")
async def delete_space_endpoint(space_id: str):
    return await _delete_space_and_related_data(space_id)


@router.post("/spaces/{space_id}/delete")
async def delete_space_endpoint_fallback(space_id: str):
    return await _delete_space_and_related_data(space_id)


@router.get("/stats", response_model=KnowledgeBaseStats)
async def get_stats():
    """Get knowledge base statistics."""
    docs = list_documents()
    flat_spaces = list_knowledge_spaces()
    return KnowledgeBaseStats(
        total_chunks=collection_count(),
        total_documents=len(docs),
    )
