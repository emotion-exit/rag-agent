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
    get_knowledge_space,
    list_knowledge_spaces,
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
    get_document_chunks,
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
    category: str = ""
    topic: str = ""
    tags: str = ""
    version_label: str = ""
    image_count: int = 0
    space_id: str = ""
    parent_space_id: str = ""


class KnowledgeSpaceCreateRequest(BaseModel):
    name: str
    parent_id: str = ""
    category: str
    topic: str
    tags: str = ""
    version_label: str = ""
    description: str = ""


class MigrateUngroupedDocumentsRequest(BaseModel):
    target_space_id: str


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


def _build_space_tree(flat_spaces: list[dict], documents: list[dict]) -> tuple[list[dict], dict[str, int], int]:
    direct_document_counts: dict[str, int] = {}
    for doc in documents:
        space_id = _normalize_metadata_value(doc.get("space_id"))
        if not space_id:
            continue
        direct_document_counts[space_id] = direct_document_counts.get(space_id, 0) + 1

    space_map = {
        item["space_id"]: {
            **item,
            "child_count": 0,
            "direct_document_count": direct_document_counts.get(item["space_id"], 0),
            "total_document_count": 0,
            "children": [],
        }
        for item in flat_spaces
    }

    roots: list[dict] = []
    for item in space_map.values():
        parent_id = _normalize_metadata_value(item.get("parent_id"))
        if parent_id and parent_id in space_map:
            space_map[parent_id]["children"].append(item)
            space_map[parent_id]["child_count"] += 1
        else:
            roots.append(item)

    def finalize(node: dict) -> int:
        total = int(node.get("direct_document_count", 0) or 0)
        children = sorted(node.get("children", []), key=lambda child: child.get("path", ""))
        node["children"] = children
        for child in children:
            total += finalize(child)
        node["total_document_count"] = total
        return total

    total_spaces = 0
    for root in sorted(roots, key=lambda item: item.get("path", "")):
        total_spaces += 1
        stack = [root]
        while stack:
            current = stack.pop()
            stack.extend(current.get("children", []))
            if current is not root:
                total_spaces += 1
        finalize(root)

    return sorted(roots, key=lambda item: item.get("path", "")), direct_document_counts, total_spaces


@router.get("/spaces")
async def get_spaces():
    docs = list_documents()
    flat_spaces = list_knowledge_spaces()
    space_tree, _, total_spaces = _build_space_tree(flat_spaces, docs)
    ungrouped_documents = sum(1 for doc in docs if not _normalize_metadata_value(doc.get("space_id")))

    return {
        "spaces": space_tree,
        "flat_spaces": flat_spaces,
        "summary": {
            "total_spaces": total_spaces,
            "ungrouped_documents": ungrouped_documents,
        },
    }


@router.post("/spaces")
async def create_space(payload: KnowledgeSpaceCreateRequest):
    try:
        space = create_knowledge_space(
            name=payload.name,
            parent_id=payload.parent_id,
            category=payload.category,
            topic=payload.topic,
            tags=payload.tags,
            version_label=payload.version_label,
            description=payload.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "success": True,
        "space": space,
        "message": f"知识空间“{space['path']}”已创建",
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


def _build_document_chunk_metadatas(
    *,
    doc_id: str,
    filename: str,
    upload_time: str,
    space_id: str,
    parent_space_id: str,
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
            "category": semantic_metadata["category"],
            "topic": semantic_metadata["topic"],
            "tags": semantic_metadata["tags"],
            "version_label": semantic_metadata["version_label"],
            "space_id": space_id,
            "parent_space_id": parent_space_id,
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


def _prepare_stored_chunks_for_migration(stored_chunks: list[dict]) -> list[dict]:
    prepared_chunks: list[dict] = []

    for item in stored_chunks:
        metadata = item.get("metadata", {}) or {}
        prepared_chunks.append(
            {
                "content": str(item.get("content", "") or ""),
                "source_type": metadata.get("source_type", "text"),
                "source_label": metadata.get("source_label", "正文文本"),
                "source_page": int(metadata.get("source_page", 0) or 0),
                "section_title": metadata.get("section_title", ""),
                "heading_path": metadata.get("heading_path", ""),
                "paragraph_index_start": int(metadata.get("paragraph_index_start", 0) or 0),
                "paragraph_index_end": int(metadata.get("paragraph_index_end", 0) or 0),
                "block_index_start": int(metadata.get("block_index_start", 0) or 0),
                "block_index_end": int(metadata.get("block_index_end", 0) or 0),
            }
        )

    return prepared_chunks


def _resolve_semantic_metadata(
    *,
    space_id: str,
    knowledge_space: str,
    category: str,
    topic: str,
    tags: str,
    version_label: str,
) -> tuple[dict[str, str], str, str]:
    normalized_space_id = _normalize_metadata_value(space_id)
    parent_space_id = ""

    if normalized_space_id:
        space = get_knowledge_space(normalized_space_id)
        if space is None:
            raise HTTPException(status_code=404, detail="知识空间不存在，请先创建后再上传文档")

        normalized_knowledge_space = _require_metadata_value("知识空间", str(space.get("path", "")))
        normalized_category = _require_metadata_value("分类", str(space.get("category", "")))
        normalized_topic = _require_metadata_value("主题", str(space.get("topic", "")))
        normalized_tags = _merge_tag_values(str(space.get("tags", "")), tags)
        normalized_version_label = _normalize_metadata_value(version_label) or _normalize_metadata_value(
            str(space.get("version_label", ""))
        )
        parent_space_id = _normalize_metadata_value(str(space.get("parent_id", "")))
    else:
        normalized_knowledge_space = _require_metadata_value("知识空间", knowledge_space)
        normalized_category = _require_metadata_value("分类", category)
        normalized_topic = _require_metadata_value("主题", topic)
        normalized_tags = _normalize_metadata_value(tags)
        normalized_version_label = _normalize_metadata_value(version_label)

    return (
        {
            "knowledge_space": normalized_knowledge_space,
            "category": normalized_category,
            "topic": normalized_topic,
            "tags": normalized_tags,
            "version_label": normalized_version_label,
        },
        normalized_space_id,
        parent_space_id,
    )


def _store_uploaded_document(
    *,
    file_bytes: bytes,
    filename: str,
    space_id: str,
    knowledge_space: str = "",
    category: str = "",
    topic: str = "",
    tags: str = "",
    version_label: str = "",
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
    semantic_metadata, normalized_space_id, parent_space_id = _resolve_semantic_metadata(
        space_id=space_id,
        knowledge_space=knowledge_space,
        category=category,
        topic=topic,
        tags=tags,
        version_label=version_label,
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
        parent_space_id=parent_space_id,
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
    version_label: str,
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
                version_label=version_label,
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


def _run_migration_job(*, job_id: str, target_space_id: str) -> None:
    update_job(job_id, status="running", message="迁移任务已开始。")
    target_space = get_knowledge_space(target_space_id)
    if target_space is None:
        fail_job(job_id, error_message="目标知识空间不存在")
        return

    docs = [doc for doc in list_documents() if not _normalize_metadata_value(doc.get("space_id"))]
    migrated_documents = 0
    migrated_chunks = 0

    try:
        for doc in docs:
            doc_id = _normalize_metadata_value(str(doc.get("doc_id", "")))
            if not doc_id:
                continue

            filename = _normalize_metadata_value(str(doc.get("filename", ""))) or "unknown"
            update_job(
                job_id,
                current_document=filename,
                message=f"正在迁移：{filename}",
            )

            stored_chunks = get_document_chunks(doc_id)
            if not stored_chunks:
                raise HTTPException(status_code=500, detail=f"文档 {doc_id} 缺少可迁移的文本块，无法重建索引")

            upload_time = _normalize_metadata_value(str(doc.get("upload_time", ""))) or datetime.now(timezone.utc).isoformat()
            existing_tags = _normalize_metadata_value(str(doc.get("tags", "")))
            existing_version_label = _normalize_metadata_value(str(doc.get("version_label", "")))
            image_count = int(doc.get("image_count", 0) or 0)

            semantic_metadata = {
                "knowledge_space": _require_metadata_value("知识空间", str(target_space.get("path", ""))),
                "category": _require_metadata_value("分类", str(target_space.get("category", ""))),
                "topic": _require_metadata_value("主题", str(target_space.get("topic", ""))),
                "tags": _merge_tag_values(str(target_space.get("tags", "")), existing_tags),
                "version_label": existing_version_label or _normalize_metadata_value(str(target_space.get("version_label", ""))),
            }

            migrated_chunk_payload = _prepare_embedding_chunks(
                _prepare_stored_chunks_for_migration(stored_chunks),
                semantic_metadata,
            )
            if not migrated_chunk_payload:
                raise HTTPException(status_code=500, detail=f"文档 {filename} 迁移后无法生成索引内容")

            delete_document(doc_id)
            chunks = [chunk["content"] for chunk in migrated_chunk_payload]
            embedding_contents = [chunk["embedding_content"] for chunk in migrated_chunk_payload]
            metadatas = _build_document_chunk_metadatas(
                doc_id=doc_id,
                filename=filename,
                upload_time=upload_time,
                space_id=target_space_id,
                parent_space_id=_normalize_metadata_value(str(target_space.get("parent_id", ""))),
                semantic_metadata=semantic_metadata,
                image_count=image_count,
                chunks_with_sources=migrated_chunk_payload,
            )
            count = add_documents(
                chunks,
                metadatas,
                doc_id,
                embedding_texts=embedding_contents,
            )
            migrated_documents += 1
            migrated_chunks += count
            advance_job(
                job_id,
                documents=1,
                chunks=count,
                message=f"已迁移 {migrated_documents}/{len(docs)} 篇文档",
                current_document=filename,
            )

        complete_job(
            job_id,
            message=(
                f"已将 {migrated_documents} 篇未归类文档迁移到“{target_space.get('path', '')}”，"
                f"并重建 {migrated_chunks} 个文本块的索引。"
            ),
            result={"space_id": target_space_id},
        )
    except Exception as exc:
        logger.exception("Migration background job failed")
        fail_job(job_id, error_message=str(exc))


class KnowledgeBaseStats(BaseModel):
    total_chunks: int
    total_documents: int


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    space_id: str = Form(default=""),
    knowledge_space: str = Form(default=""),
    category: str = Form(default=""),
    topic: str = Form(default=""),
    tags: str = Form(default=""),
    version_label: str = Form(default=""),
):
    """Upload a document to the knowledge base."""
    try:
        file_bytes = await file.read()
        return _store_uploaded_document(
            file_bytes=file_bytes,
            filename=file.filename or "unknown",
            space_id=space_id,
            knowledge_space=knowledge_space,
            category=category,
            topic=topic,
            tags=tags,
            version_label=version_label,
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
    version_label: str = Form(default=""),
):
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")

    normalized_space_id = _normalize_metadata_value(space_id)
    if not normalized_space_id:
        raise HTTPException(status_code=400, detail="请先选择知识空间")

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
            version_label=version_label,
        )
    )
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "message": job["message"],
    }


@router.post("/documents/migrate-ungrouped")
async def migrate_ungrouped_documents(payload: MigrateUngroupedDocumentsRequest):
    target_space_id = _normalize_metadata_value(payload.target_space_id)
    if not target_space_id:
        raise HTTPException(status_code=400, detail="目标知识空间不能为空")

    target_space = get_knowledge_space(target_space_id)
    if target_space is None:
        raise HTTPException(status_code=404, detail="目标知识空间不存在")

    docs = [doc for doc in list_documents() if not _normalize_metadata_value(doc.get("space_id"))]
    if not docs:
        return {
            "success": True,
            "migrated_documents": 0,
            "migrated_chunks": 0,
            "message": "当前没有未归类文档需要迁移。",
        }

    prepared_payloads: list[dict] = []
    for doc in docs:
        doc_id = _normalize_metadata_value(str(doc.get("doc_id", "")))
        if not doc_id:
            continue

        stored_chunks = get_document_chunks(doc_id)
        if not stored_chunks:
            raise HTTPException(status_code=500, detail=f"文档 {doc_id} 缺少可迁移的文本块，无法重建索引")

        filename = _normalize_metadata_value(str(doc.get("filename", ""))) or "unknown"
        upload_time = _normalize_metadata_value(str(doc.get("upload_time", ""))) or datetime.now(timezone.utc).isoformat()
        existing_tags = _normalize_metadata_value(str(doc.get("tags", "")))
        existing_version_label = _normalize_metadata_value(str(doc.get("version_label", "")))
        image_count = int(doc.get("image_count", 0) or 0)

        semantic_metadata = {
            "knowledge_space": _require_metadata_value("知识空间", str(target_space.get("path", ""))),
            "category": _require_metadata_value("分类", str(target_space.get("category", ""))),
            "topic": _require_metadata_value("主题", str(target_space.get("topic", ""))),
            "tags": _merge_tag_values(str(target_space.get("tags", "")), existing_tags),
            "version_label": existing_version_label or _normalize_metadata_value(str(target_space.get("version_label", ""))),
        }

        migrated_chunks = _prepare_embedding_chunks(
            _prepare_stored_chunks_for_migration(stored_chunks),
            semantic_metadata,
        )
        if not migrated_chunks:
            raise HTTPException(status_code=500, detail=f"文档 {filename} 迁移后无法生成索引内容")

        prepared_payloads.append(
            {
                "doc_id": doc_id,
                "filename": filename,
                "upload_time": upload_time,
                "space_id": target_space_id,
                "parent_space_id": _normalize_metadata_value(str(target_space.get("parent_id", ""))),
                "semantic_metadata": semantic_metadata,
                "image_count": image_count,
                "chunks_with_sources": migrated_chunks,
            }
        )

    migrated_documents = 0
    migrated_chunks = 0

    try:
        for item in prepared_payloads:
            delete_document(item["doc_id"])
            chunks = [chunk["content"] for chunk in item["chunks_with_sources"]]
            embedding_contents = [chunk["embedding_content"] for chunk in item["chunks_with_sources"]]
            metadatas = _build_document_chunk_metadatas(
                doc_id=item["doc_id"],
                filename=item["filename"],
                upload_time=item["upload_time"],
                space_id=item["space_id"],
                parent_space_id=item["parent_space_id"],
                semantic_metadata=item["semantic_metadata"],
                image_count=item["image_count"],
                chunks_with_sources=item["chunks_with_sources"],
            )
            count = add_documents(
                chunks,
                metadatas,
                item["doc_id"],
                embedding_texts=embedding_contents,
            )
            migrated_documents += 1
            migrated_chunks += count
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to migrate ungrouped documents to space '%s'", target_space_id)
        raise HTTPException(status_code=500, detail=f"迁移未归类文档失败：{exc}") from exc

    return {
        "success": True,
        "migrated_documents": migrated_documents,
        "migrated_chunks": migrated_chunks,
        "message": (
            f"已将 {migrated_documents} 篇未归类文档迁移到“{target_space.get('path', '')}”，"
            f"并重建 {migrated_chunks} 个文本块的索引。"
        ),
    }


@router.post("/documents/migrate-ungrouped/jobs", response_model=KnowledgeBaseJobCreatedResponse)
async def create_migrate_ungrouped_job(payload: MigrateUngroupedDocumentsRequest):
    target_space_id = _normalize_metadata_value(payload.target_space_id)
    if not target_space_id:
        raise HTTPException(status_code=400, detail="目标知识空间不能为空")

    target_space = get_knowledge_space(target_space_id)
    if target_space is None:
        raise HTTPException(status_code=404, detail="目标知识空间不存在")

    docs = [doc for doc in list_documents() if not _normalize_metadata_value(doc.get("space_id"))]
    if not docs:
        raise HTTPException(status_code=400, detail="当前没有未归类文档需要迁移")

    estimated_chunks = sum(int(doc.get("chunk_count", 0) or 0) for doc in docs)
    job = create_job(
        job_type="migrate_ungrouped",
        total_documents=len(docs),
        total_chunks=estimated_chunks,
        message="迁移任务已创建，等待后台处理。",
    )
    asyncio.create_task(
        asyncio.to_thread(
            _run_migration_job,
            job_id=job["job_id"],
            target_space_id=target_space_id,
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
            "category": doc.get("category", ""),
            "topic": doc.get("topic", ""),
            "tags": doc.get("tags", ""),
            "version_label": doc.get("version_label", ""),
            "image_count": int(doc.get("image_count", 0) or 0),
            "space_id": doc.get("space_id", ""),
            "parent_space_id": doc.get("parent_space_id", ""),
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
    flat_spaces = list_knowledge_spaces()
    return KnowledgeBaseStats(
        total_chunks=collection_count(),
        total_documents=len(docs),
    )
