import io

from app.services.document_processors.common import (
    Block,
    build_anchor_text,
    find_nearest_pdf_blocks,
    guess_content_type,
    infer_heading_level,
    load_pymupdf,
    looks_like_heading,
    normalize_block,
    split_blocks_into_sections,
    update_heading_stack,
)


def extract_pdf(file_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    texts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            texts.append(text.strip())
    return "\n\n".join(texts)


def extract_pdf_sections(file_bytes: bytes) -> list[dict]:
    fitz = load_pymupdf()

    document = fitz.open(stream=file_bytes, filetype="pdf")
    sections: list[dict] = []

    try:
        for page_number in range(1, len(document) + 1):
            page = document.load_page(page_number - 1)
            page_blocks = extract_pdf_text_blocks(page, page_number)
            if not page_blocks:
                continue

            sections.extend(
                split_blocks_into_sections(
                    page_blocks,
                    source_label=f"第 {page_number} 页正文",
                    source_page=page_number,
                )
            )
    finally:
        document.close()

    return sections


def extract_pdf_images(file_bytes: bytes) -> list[dict]:
    fitz = load_pymupdf()

    document = fitz.open(stream=file_bytes, filetype="pdf")
    images: list[dict] = []

    try:
        for page_number in range(1, len(document) + 1):
            page = document.load_page(page_number - 1)
            text_blocks = extract_pdf_text_blocks(page, page_number)
            seen_xrefs: set[int] = set()

            for image_index, image_info in enumerate(page.get_images(full=True), start=1):
                xref = int(image_info[0])
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)

                image_data = document.extract_image(xref)
                image_bytes = image_data.get("image")
                if not image_bytes:
                    continue

                rects = page.get_image_rects(xref)
                bbox = rects[0] if rects else None
                anchor_before, anchor_after = find_nearest_pdf_blocks(text_blocks, bbox)
                nearest_block = anchor_before or anchor_after
                ext = str(image_data.get("ext", "png")).lower()

                images.append(
                    {
                        "filename": f"page-{page_number}-image-{image_index}.{ext}",
                        "bytes": image_bytes,
                        "content_type": guess_content_type(ext),
                        "source_label": f"第 {page_number} 页图片 {image_index}",
                        "source_page": page_number,
                        "block_index": int((nearest_block or {}).get("block_index", 0) or 0),
                        "anchor_before": str((anchor_before or {}).get("text", "")),
                        "anchor_after": str((anchor_after or {}).get("text", "")),
                        "anchor_text": build_anchor_text(anchor_before, anchor_after),
                        "heading_path": str((nearest_block or {}).get("heading_path", "")),
                        "section_title": str((nearest_block or {}).get("section_title", "")),
                    }
                )
    finally:
        document.close()

    return images


def extract_pdf_text_blocks(page, page_number: int) -> list[Block]:
    blocks: list[Block] = []
    heading_stack: list[str] = []
    current_title = ""
    block_index = 0

    for raw_block in page.get_text("blocks", sort=True):
        if len(raw_block) < 5:
            continue
        if len(raw_block) >= 7 and int(raw_block[6]) != 0:
            continue

        text = normalize_block(str(raw_block[4]))
        if not text:
            continue

        block_index += 1
        if looks_like_heading(text):
            level = infer_heading_level(text)
            heading_stack = update_heading_stack(heading_stack, text, level)
            current_title = text
            continue

        blocks.append(
            {
                "text": text,
                "paragraph_index": block_index,
                "block_index": block_index,
                "source_page": page_number,
                "bbox": (
                    float(raw_block[0]),
                    float(raw_block[1]),
                    float(raw_block[2]),
                    float(raw_block[3]),
                ),
                "heading_path": " > ".join(heading_stack),
                "section_title": current_title,
            }
        )

    return blocks
