import os

from app.services.document_processors import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    SUPPORTED_DOCUMENT_EXTENSIONS,
    extract_text,
    extract_text_sections,
    get_processor_for_extension,
)
from app.services.document_processors.common import chunk_section_blocks


TEXT_SOURCE_TYPE = "text"


def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from supported file types."""
    ext = os.path.splitext(filename)[1].lower()
    processor = get_processor_for_extension(ext)
    if processor is None:
        return extract_text(file_bytes)
    return processor.text_extractor(file_bytes)


def extract_document_chunks(
    file_bytes: bytes,
    filename: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict]:
    sections = extract_document_sections(file_bytes, filename)
    chunks: list[dict] = []

    for section in sections:
        blocks = list(section.get("blocks", []))
        if not blocks:
            continue

        for chunk in chunk_section_blocks(
            blocks,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        ):
            chunks.append(
                {
                    "content": chunk["content"],
                    "source_type": TEXT_SOURCE_TYPE,
                    "source_label": str(section.get("source_label", "正文文本")),
                    "source_page": int(section.get("source_page", 0) or 0),
                    "section_title": str(section.get("section_title", "")).strip(),
                    "heading_path": str(section.get("heading_path", "")).strip(),
                    "paragraph_index_start": int(chunk.get("paragraph_index_start", 0) or 0),
                    "paragraph_index_end": int(chunk.get("paragraph_index_end", 0) or 0),
                    "block_index_start": int(chunk.get("block_index_start", 0) or 0),
                    "block_index_end": int(chunk.get("block_index_end", 0) or 0),
                }
            )

    return chunks


def extract_document_sections(file_bytes: bytes, filename: str) -> list[dict]:
    ext = os.path.splitext(filename)[1].lower()
    processor = get_processor_for_extension(ext)
    if processor is None:
        return extract_text_sections(
            extract_text(file_bytes),
            source_label="正文文本",
        )
    return processor.sections_extractor(file_bytes)


def extract_document_images(file_bytes: bytes, filename: str) -> list[dict]:
    ext = os.path.splitext(filename)[1].lower()
    processor = get_processor_for_extension(ext)
    if processor is None or processor.images_extractor is None:
        return []
    return processor.images_extractor(file_bytes)


__all__ = [
    "DEFAULT_CHUNK_OVERLAP",
    "DEFAULT_CHUNK_SIZE",
    "SUPPORTED_DOCUMENT_EXTENSIONS",
    "TEXT_SOURCE_TYPE",
    "extract_document_chunks",
    "extract_document_images",
    "extract_document_sections",
    "extract_text_from_file",
]
