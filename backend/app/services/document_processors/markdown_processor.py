import re

from app.services.document_processors.common import Block, normalize_block, split_blocks_into_sections
from app.services.document_processors.text_processor import extract_text


MARKDOWN_EXTENSIONS = {".md", ".markdown"}


def extract_markdown(file_bytes: bytes) -> str:
    return "\n\n".join(
        section.get("content", "").strip()
        for section in extract_markdown_sections(file_bytes)
        if str(section.get("content", "")).strip()
    ).strip()


def extract_markdown_sections(file_bytes: bytes) -> list[dict]:
    text = extract_text(file_bytes).replace("\r\n", "\n").replace("\r", "\n")
    blocks: list[Block] = []
    paragraph_lines: list[str] = []
    paragraph_index = 0
    block_index = 0
    in_code_fence = False

    def append_block(block_text: str) -> None:
        nonlocal paragraph_index, block_index
        normalized = normalize_block(block_text)
        if not normalized:
            return

        paragraph_index += 1
        block_index += 1
        blocks.append(
            {
                "text": normalized,
                "paragraph_index": paragraph_index,
                "block_index": block_index,
            }
        )

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if not paragraph_lines:
            return
        append_block("\n".join(paragraph_lines))
        paragraph_lines = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if re.match(r"^(```+|~~~+)", stripped):
            flush_paragraph()
            in_code_fence = not in_code_fence
            continue

        if not stripped:
            flush_paragraph()
            continue

        if in_code_fence:
            cleaned_code = clean_markdown_line(line, in_code_block=True)
            if cleaned_code:
                paragraph_lines.append(cleaned_code)
            continue

        if is_markdown_heading_line(stripped):
            flush_paragraph()
            heading_text = normalize_markdown_heading(stripped)
            if heading_text:
                append_block(heading_text)
            continue

        if is_markdown_thematic_break(stripped):
            flush_paragraph()
            continue

        cleaned_line = clean_markdown_line(line)
        if not cleaned_line:
            flush_paragraph()
            continue

        if starts_markdown_standalone_block(stripped):
            flush_paragraph()
            append_block(cleaned_line)
            continue

        paragraph_lines.append(cleaned_line)

    flush_paragraph()

    if not blocks:
        return []

    return split_blocks_into_sections(
        blocks,
        source_label="正文文本",
        source_page=0,
    )


def is_markdown_heading_line(line: str) -> bool:
    return bool(re.match(r"^#{1,6}\s+\S+", line.strip()))


def normalize_markdown_heading(line: str) -> str:
    stripped = line.strip()
    match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
    if not match:
        return clean_markdown_line(stripped)

    hashes, title = match.groups()
    cleaned_title = clean_markdown_inline(title)
    if not cleaned_title:
        return ""
    return f"{hashes} {cleaned_title}".strip()


def is_markdown_thematic_break(line: str) -> bool:
    return bool(re.match(r"^\s{0,3}(?:[-*_]\s*){3,}$", line))


def starts_markdown_standalone_block(line: str) -> bool:
    stripped = line.strip()
    return bool(
        re.match(r"^(?:[-*+]\s+|\d+[.)]\s+|>\s*)", stripped)
        or ("|" in stripped and stripped.count("|") >= 2)
    )


def clean_markdown_inline(text: str) -> str:
    cleaned = text or ""
    cleaned = re.sub(r"!\[([^\]]*)\]\([^\)]*\)", r"\1", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]*\)", r"\1", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", cleaned)
    cleaned = re.sub(r"<((?:https?|mailto):[^>]+)>", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
    cleaned = re.sub(r"(\*\*|__|~~)", "", cleaned)
    cleaned = re.sub(r"(?<!\*)\*(?!\*)([^*]+?)(?<!\*)\*(?!\*)", r"\1", cleaned)
    cleaned = re.sub(r"(?<!_)_(?!_)([^_]+?)(?<!_)_(?!_)", r"\1", cleaned)
    cleaned = re.sub(r"\\([`*_{}\[\]()#+\-.!|>~])", r"\1", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def clean_markdown_line(line: str, *, in_code_block: bool = False) -> str:
    stripped = line.strip()
    if not stripped:
        return ""

    if re.match(r"^\[[^\]]+\]:\s+\S+", stripped):
        return ""

    if in_code_block:
        return re.sub(r"\s+", " ", stripped).strip()

    stripped = re.sub(r"^>+\s*", "", stripped)
    stripped = re.sub(r"^[-*+]\s+", "", stripped)
    stripped = re.sub(r"^\d+[.)]\s+", "", stripped)

    if "|" in stripped and stripped.count("|") >= 2:
        if is_markdown_thematic_break(stripped.replace("|", "")):
            return ""
        cells = [clean_markdown_inline(cell) for cell in stripped.strip("|").split("|")]
        stripped = " | ".join(cell for cell in cells if cell)
        return re.sub(r"\s+", " ", stripped).strip()

    return clean_markdown_inline(stripped)
