import os
import re
from importlib import import_module


DEFAULT_CHUNK_SIZE = 240
DEFAULT_CHUNK_OVERLAP = 24
TITLE_MAX_LENGTH = 80


Block = dict[str, int | str | tuple[float, float, float, float]]
Section = dict[str, object]
ImageInfo = dict[str, object]


def normalize_block(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def join_blocks(blocks: list[str]) -> str:
    return "\n\n".join(block for block in blocks if block).strip()


def build_section_payload(
    blocks: list[Block],
    section_title: str,
    heading_path: str,
    source_label: str,
    source_page: int,
) -> Section:
    return {
        "blocks": blocks,
        "content": join_blocks([str(block.get("text", "")) for block in blocks]),
        "section_title": section_title,
        "heading_path": heading_path,
        "source_label": source_label,
        "source_page": source_page,
        "paragraph_index_start": range_start(blocks, "paragraph_index"),
        "paragraph_index_end": range_end(blocks, "paragraph_index"),
        "block_index_start": range_start(blocks, "block_index"),
        "block_index_end": range_end(blocks, "block_index"),
    }


def split_blocks_into_sections(
    blocks: list[Block],
    source_label: str,
    source_page: int,
) -> list[Section]:
    sections: list[Section] = []
    heading_stack: list[str] = []
    current_title = ""
    current_blocks: list[Block] = []

    def flush_current_section() -> None:
        nonlocal current_blocks
        if not current_blocks:
            return

        sections.append(
            build_section_payload(
                blocks=current_blocks,
                section_title=current_title,
                heading_path=" > ".join(heading_stack),
                source_label=current_title or source_label,
                source_page=source_page,
            )
        )
        current_blocks = []

    for block in blocks:
        text = normalize_block(str(block.get("text", "")))
        if looks_like_heading(text):
            flush_current_section()
            level = infer_heading_level(text)
            heading_stack = update_heading_stack(heading_stack, text, level)
            current_title = text
            continue

        current_blocks.append(block)

    flush_current_section()

    return sections or [
        build_section_payload(
            blocks=blocks,
            section_title="",
            heading_path="",
            source_label=source_label,
            source_page=source_page,
        )
    ]


def chunk_section_blocks(
    blocks: list[Block],
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict]:
    units: list[Block] = []
    for block in blocks:
        text = str(block.get("text", ""))
        if len(text) <= chunk_size:
            units.append(block)
        else:
            units.extend(split_long_block(block, chunk_size))

    chunks: list[dict] = []
    current_units: list[Block] = []

    for unit in units:
        candidate_units = current_units + [unit]
        candidate_length = len(join_blocks([str(item.get("text", "")) for item in candidate_units]))

        if current_units and candidate_length > chunk_size:
            chunks.append(build_chunk_payload(current_units))
            current_units = fit_overlap_units(
                collect_overlap_units(current_units, chunk_overlap),
                next_unit=unit,
                chunk_size=chunk_size,
            )

        current_units.append(unit)

    if current_units:
        chunks.append(build_chunk_payload(current_units))

    return chunks


def build_chunk_payload(units: list[Block]) -> dict:
    return {
        "content": join_blocks([str(unit.get("text", "")) for unit in units]),
        "paragraph_index_start": range_start(units, "paragraph_index"),
        "paragraph_index_end": range_end(units, "paragraph_index"),
        "block_index_start": range_start(units, "block_index"),
        "block_index_end": range_end(units, "block_index"),
    }


def split_long_block(block: Block, chunk_size: int) -> list[Block]:
    text = str(block.get("text", ""))
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[。！？!?；;])\s+|(?<=[。！？!?；;])", text)
        if sentence.strip()
    ]

    if len(sentences) <= 1:
        return [
            {
                **block,
                "text": text[index : index + chunk_size].strip(),
            }
            for index in range(0, len(text), chunk_size)
            if text[index : index + chunk_size].strip()
        ]

    pieces: list[Block] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current}{sentence}" if current else sentence
        if current and len(candidate) > chunk_size:
            pieces.append({**block, "text": current.strip()})
            current = sentence
        else:
            current = candidate

    if current.strip():
        pieces.append({**block, "text": current.strip()})

    return pieces


def collect_overlap_units(units: list[Block], overlap_chars: int) -> list[Block]:
    if overlap_chars <= 0:
        return []

    overlap: list[Block] = []
    total = 0
    for unit in reversed(units):
        overlap.insert(0, unit)
        total += len(str(unit.get("text", "")))
        if total >= overlap_chars:
            break

    return overlap


def fit_overlap_units(
    overlap_units: list[Block],
    next_unit: Block,
    chunk_size: int,
) -> list[Block]:
    fitted = list(overlap_units)
    next_text = str(next_unit.get("text", ""))

    while fitted:
        candidate_texts = [str(unit.get("text", "")) for unit in fitted] + [next_text]
        if len(join_blocks(candidate_texts)) <= chunk_size:
            break
        fitted.pop(0)

    return fitted


def find_meaningful_paragraph(sequence: list[dict], index: int, direction: int) -> dict | None:
    cursor = index + direction
    while 0 <= cursor < len(sequence):
        item = sequence[cursor]
        if item.get("type") == "paragraph" and is_meaningful_anchor_text(str(item.get("text", ""))):
            return item
        cursor += direction
    return None


def is_meaningful_anchor_text(text: str) -> bool:
    normalized = normalize_block(text)
    if len(normalized) < 4:
        return False
    meaningless = {"如下图", "见下图", "如下", "见图", "如图", "如下所示", "见下页"}
    return normalized not in meaningless


def build_anchor_text(anchor_before: dict | None, anchor_after: dict | None) -> str:
    texts = []
    if anchor_before is not None:
        texts.append(str(anchor_before.get("text", "")).strip())
    if anchor_after is not None:
        after_text = str(anchor_after.get("text", "")).strip()
        if after_text and after_text not in texts:
            texts.append(after_text)
    return "\n".join(text for text in texts if text)


def find_nearest_pdf_blocks(
    text_blocks: list[Block],
    image_bbox,
) -> tuple[Block | None, Block | None]:
    if image_bbox is None:
        return None, None

    image_center_y = (float(image_bbox.y0) + float(image_bbox.y1)) / 2
    before_candidates = []
    after_candidates = []

    for block in text_blocks:
        bbox = block.get("bbox")
        if not isinstance(bbox, tuple) or len(bbox) != 4:
            continue

        block_center_y = (float(bbox[1]) + float(bbox[3])) / 2
        delta = abs(block_center_y - image_center_y)
        if block_center_y <= image_center_y:
            before_candidates.append((delta, block))
        else:
            after_candidates.append((delta, block))

    before_candidates.sort(key=lambda item: item[0])
    after_candidates.sort(key=lambda item: item[0])
    before = before_candidates[0][1] if before_candidates else None
    after = after_candidates[0][1] if after_candidates else None
    return before, after


def range_start(items: list[Block], key: str) -> int:
    values = [int(item.get(key, 0) or 0) for item in items if int(item.get(key, 0) or 0) > 0]
    return min(values) if values else 0


def range_end(items: list[Block], key: str) -> int:
    values = [int(item.get(key, 0) or 0) for item in items if int(item.get(key, 0) or 0) > 0]
    return max(values) if values else 0


def guess_content_type(name_or_ext: str) -> str:
    ext = os.path.splitext(name_or_ext)[1].lower() if "." in name_or_ext else f'.{name_or_ext.lower()}'
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".gif":
        return "image/gif"
    if ext == ".webp":
        return "image/webp"
    if ext == ".bmp":
        return "image/bmp"
    return "image/png"


def looks_like_heading(text: str) -> bool:
    normalized = normalize_block(text)
    if not normalized or len(normalized) > TITLE_MAX_LENGTH:
        return False
    if normalized.endswith(("。", "；", ";", ":", "：")):
        return False
    patterns = (
        r"^#{1,6}\s+.+$",
        r"^第[一二三四五六七八九十百0-9]+[章节部分篇]\s*.*$",
        r"^[一二三四五六七八九十]+[、.]\s*.+$",
        r"^[0-9]+(?:\.[0-9]+){0,3}\s+.+$",
        r"^[0-9]+[、.)]\s*.+$",
        r"^[（(][0-9一二三四五六七八九十]+[）)]\s*.+$",
    )
    return any(re.match(pattern, normalized) for pattern in patterns)


def infer_heading_level(text: str) -> int:
    normalized = normalize_block(text)
    if re.match(r"^#{1,6}\s+.+$", normalized):
        return min(len(normalized) - len(normalized.lstrip("#")), 6)
    if re.match(r"^第[一二三四五六七八九十百0-9]+[章节部分篇]", normalized):
        return 1
    if re.match(r"^[一二三四五六七八九十]+[、.]", normalized):
        return 2
    if re.match(r"^[0-9]+\.[0-9]+\.[0-9]+", normalized):
        return 4
    if re.match(r"^[0-9]+\.[0-9]+", normalized):
        return 3
    if re.match(r"^[0-9]+[、.)]", normalized):
        return 3
    if re.match(r"^[（(][0-9一二三四五六七八九十]+[）)]", normalized):
        return 4
    return 2


def update_heading_stack(stack: list[str], heading: str, level: int) -> list[str]:
    normalized_heading = normalize_block(heading)
    next_stack = list(stack[: max(level - 1, 0)])
    next_stack.append(normalized_heading)
    return next_stack


def load_pymupdf():
    for module_name in ("fitz", "pymupdf"):
        try:
            return import_module(module_name)
        except ModuleNotFoundError:
            continue

    raise RuntimeError(
        "PDF 解析依赖未安装，请在 backend 环境中执行 `pip install pymupdf` "
        "或重新同步 `pyproject.toml` 依赖后再试。"
    )
