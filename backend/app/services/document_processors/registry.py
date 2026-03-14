from dataclasses import dataclass
from typing import Callable

from app.services.document_processors.markdown_processor import (
    MARKDOWN_EXTENSIONS,
    extract_markdown,
    extract_markdown_sections,
)
from app.services.document_processors.docx_processor import (
    extract_docx,
    extract_docx_images,
    extract_docx_sections,
)
from app.services.document_processors.pdf_processor import (
    extract_pdf,
    extract_pdf_images,
    extract_pdf_sections,
)
from app.services.document_processors.text_processor import extract_text, extract_text_sections


@dataclass(frozen=True)
class DocumentProcessorSpec:
    extensions: frozenset[str]
    text_extractor: Callable[[bytes], str]
    sections_extractor: Callable[[bytes], list[dict]]
    images_extractor: Callable[[bytes], list[dict]] | None = None


PROCESSOR_REGISTRY: tuple[DocumentProcessorSpec, ...] = (
    DocumentProcessorSpec(
        extensions=frozenset({".pdf"}),
        text_extractor=extract_pdf,
        sections_extractor=extract_pdf_sections,
        images_extractor=extract_pdf_images,
    ),
    DocumentProcessorSpec(
        extensions=frozenset({".docx"}),
        text_extractor=extract_docx,
        sections_extractor=extract_docx_sections,
        images_extractor=extract_docx_images,
    ),
    DocumentProcessorSpec(
        extensions=frozenset(MARKDOWN_EXTENSIONS),
        text_extractor=extract_markdown,
        sections_extractor=extract_markdown_sections,
        images_extractor=None,
    ),
    DocumentProcessorSpec(
        extensions=frozenset({".txt", ".rst", ".csv"}),
        text_extractor=extract_text,
        sections_extractor=lambda file_bytes: extract_text_sections(
            extract_text(file_bytes),
            source_label="正文文本",
        ),
        images_extractor=None,
    ),
)

SUPPORTED_DOCUMENT_EXTENSIONS: frozenset[str] = frozenset(
    extension
    for processor in PROCESSOR_REGISTRY
    for extension in processor.extensions
)


def get_processor_for_extension(extension: str) -> DocumentProcessorSpec | None:
    normalized_extension = extension.strip().lower()
    for processor in PROCESSOR_REGISTRY:
        if normalized_extension in processor.extensions:
            return processor
    return None
