import json
import os
import shutil

from app.config import settings


MANIFEST_FILE = "images.json"


def _document_dir(doc_id: str) -> str:
    return os.path.join(settings.upload_dir, doc_id)


def _images_dir(doc_id: str) -> str:
    return os.path.join(_document_dir(doc_id), "images")


def save_document_images(doc_id: str, images: list[dict]) -> list[dict]:
    if not images:
        delete_document_assets(doc_id)
        return []

    os.makedirs(_images_dir(doc_id), exist_ok=True)
    manifest: list[dict] = []

    for index, image in enumerate(images, start=1):
        original_name = str(image.get("filename", f"image-{index}.png"))
        ext = os.path.splitext(original_name)[1].lower() or ".png"
        image_id = f"image-{index}"
        stored_name = f"{image_id}{ext}"
        file_path = os.path.join(_images_dir(doc_id), stored_name)

        with open(file_path, "wb") as handle:
            handle.write(image.get("bytes", b""))

        manifest.append(
            {
                "image_id": image_id,
                "stored_name": stored_name,
                "filename": original_name,
                "content_type": image.get("content_type", "image/png"),
                "source_label": image.get("source_label", f"文档图片 {index}"),
                "source_page": int(image.get("source_page", 0) or 0),
                "paragraph_index": int(image.get("paragraph_index", 0) or 0),
                "block_index": int(image.get("block_index", 0) or 0),
                "anchor_before": str(image.get("anchor_before", "") or ""),
                "anchor_after": str(image.get("anchor_after", "") or ""),
                "anchor_text": str(image.get("anchor_text", "") or ""),
                "heading_path": str(image.get("heading_path", "") or ""),
                "section_title": str(image.get("section_title", "") or ""),
            }
        )

    with open(os.path.join(_document_dir(doc_id), MANIFEST_FILE), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)

    return manifest


def list_document_images(doc_id: str) -> list[dict]:
    manifest_path = os.path.join(_document_dir(doc_id), MANIFEST_FILE)
    if not os.path.exists(manifest_path):
        return []

    with open(manifest_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    return data if isinstance(data, list) else []


def get_document_image(doc_id: str, image_id: str) -> tuple[str, dict] | None:
    for item in list_document_images(doc_id):
        if item.get("image_id") != image_id:
            continue

        file_path = os.path.join(_images_dir(doc_id), str(item.get("stored_name", "")))
        if os.path.exists(file_path):
            return file_path, item

    return None


def delete_document_assets(doc_id: str) -> None:
    doc_dir = _document_dir(doc_id)
    if os.path.exists(doc_dir):
        shutil.rmtree(doc_dir)