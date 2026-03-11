import io
import os
import zipfile

import chardet
from PIL import Image, UnidentifiedImageError

from app.config import settings


TEXT_SOURCE_TYPE = "text"
IMAGE_OCR_SOURCE_TYPE = "image_ocr"
OCR_CHUNK_SIZE = 320
OCR_CHUNK_OVERLAP = 40

_ocr_engine = None
_ocr_engine_unavailable = False


def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from supported file types."""
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".pdf":
        return _extract_pdf(file_bytes)
    if ext == ".docx":
        return _extract_docx(file_bytes)
    if ext in (".txt", ".md", ".rst", ".csv"):
        return _extract_text(file_bytes)

    return _extract_text(file_bytes)


def extract_document_chunks(
    file_bytes: bytes,
    filename: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[dict]:
    text = extract_text_from_file(file_bytes, filename)
    text_chunks = [
        {
            "content": chunk,
            "source_type": TEXT_SOURCE_TYPE,
            "source_label": "正文文本",
            "source_page": 0,
        }
        for chunk in chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    ]

    ocr_chunks = []
    for block in extract_ocr_blocks(file_bytes, filename):
        for chunk in chunk_text(
            block["text"],
            chunk_size=OCR_CHUNK_SIZE,
            chunk_overlap=OCR_CHUNK_OVERLAP,
        ):
            ocr_chunks.append(
                {
                    "content": chunk,
                    "source_type": IMAGE_OCR_SOURCE_TYPE,
                    "source_label": block["source_label"],
                    "source_page": block.get("source_page", 0),
                }
            )

    return text_chunks + ocr_chunks


def extract_ocr_blocks(file_bytes: bytes, filename: str) -> list[dict]:
    if not settings.ocr_enabled:
        return []

    ext = os.path.splitext(filename)[1].lower()
    if ext == ".docx":
        return _extract_docx_ocr_blocks(file_bytes)
    if ext == ".pdf":
        return _extract_pdf_ocr_blocks(file_bytes)
    return []


def _extract_pdf(file_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    texts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            texts.append(text.strip())
    return "\n\n".join(texts)


def _extract_docx(file_bytes: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def _extract_text(file_bytes: bytes) -> str:
    detected = chardet.detect(file_bytes)
    encoding = detected.get("encoding") or "utf-8"
    return file_bytes.decode(encoding, errors="replace")


def _extract_docx_ocr_blocks(file_bytes: bytes) -> list[dict]:
    blocks = []

    with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
        media_files = sorted(
            name for name in archive.namelist() if name.startswith("word/media/")
        )

        for index, name in enumerate(media_files, start=1):
            text = _ocr_image_bytes(archive.read(name))
            if not _is_meaningful_ocr_text(text):
                continue

            blocks.append(
                {
                    "text": text,
                    "source_label": f"截图识别 {index}",
                    "source_page": 0,
                }
            )

    return blocks


def _extract_pdf_ocr_blocks(file_bytes: bytes) -> list[dict]:
    import fitz

    blocks = []
    document = fitz.open(stream=file_bytes, filetype="pdf")

    try:
        for page_index in range(len(document)):
            page = document.load_page(page_index)
            seen_xrefs: set[int] = set()

            for image_index, image_info in enumerate(page.get_images(full=True), start=1):
                xref = int(image_info[0])
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)

                image = document.extract_image(xref)
                image_bytes = image.get("image")
                if not image_bytes:
                    continue

                text = _ocr_image_bytes(image_bytes)
                if not _is_meaningful_ocr_text(text):
                    continue

                blocks.append(
                    {
                        "text": text,
                        "source_label": f"第 {page_index + 1} 页截图 {image_index}",
                        "source_page": page_index + 1,
                    }
                )
    finally:
        document.close()

    return blocks


def _get_ocr_engine():
    global _ocr_engine, _ocr_engine_unavailable

    if _ocr_engine_unavailable:
        return None
    if _ocr_engine is not None:
        return _ocr_engine

    try:
        from rapidocr_onnxruntime import RapidOCR

        _ocr_engine = RapidOCR()
    except Exception:
        _ocr_engine_unavailable = True
        return None

    return _ocr_engine


def _ocr_image_bytes(image_bytes: bytes) -> str:
    engine = _get_ocr_engine()
    if engine is None:
        return ""

    try:
        import numpy as np

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except (UnidentifiedImageError, OSError):
        return ""

    result, _ = engine(np.array(image))
    if not result:
        return ""

    lines = []
    for item in result:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue

        text = str(item[1]).strip()
        if text:
            lines.append(text)

    return "\n".join(lines)


def _is_meaningful_ocr_text(text: str) -> bool:
    normalized = " ".join(text.split())
    return len(normalized) >= settings.ocr_min_text_length


def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks for better retrieval."""
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    step = max(chunk_size - chunk_overlap, 1)
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += step

    return chunks
