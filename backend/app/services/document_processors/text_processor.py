import re

import chardet

from app.services.document_processors.common import Block, normalize_block, split_blocks_into_sections


def extract_text(file_bytes: bytes) -> str:
    detected = chardet.detect(file_bytes)
    encoding = detected.get("encoding") or "utf-8"
    return file_bytes.decode(encoding, errors="replace")


def extract_text_sections(
    text: str,
    source_label: str,
    source_page: int = 0,
) -> list[dict]:
    paragraphs = [
        normalize_block(paragraph)
        for paragraph in re.split(r"\n\s*\n", text)
        if normalize_block(paragraph)
    ]
    if not paragraphs:
        return []

    blocks: list[Block] = [
        {
            "text": paragraph,
            "paragraph_index": index,
            "block_index": index,
        }
        for index, paragraph in enumerate(paragraphs, start=1)
    ]

    return split_blocks_into_sections(
        blocks,
        source_label=source_label,
        source_page=source_page,
    )
