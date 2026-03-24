import json
import os
import uuid
from datetime import datetime, timezone

from app.config import settings


SPACE_MANIFEST_FILE = "knowledge_spaces.json"


def _manifest_path() -> str:
    os.makedirs(settings.upload_dir, exist_ok=True)
    return os.path.join(settings.upload_dir, SPACE_MANIFEST_FILE)


def _load_raw_spaces() -> list[dict]:
    manifest_path = _manifest_path()
    if not os.path.exists(manifest_path):
        return []

    with open(manifest_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    return payload if isinstance(payload, list) else []


def _save_raw_spaces(spaces: list[dict]) -> None:
    with open(_manifest_path(), "w", encoding="utf-8") as handle:
        json.dump(spaces, handle, ensure_ascii=False, indent=2)


def _normalize_text(value: str | None) -> str:
    return str(value or "").strip()


def _split_tags(value: str | None) -> list[str]:
    raw_value = _normalize_text(value)
    if not raw_value:
        return []

    parts: list[str] = []
    seen: set[str] = set()
    for item in raw_value.replace("、", ",").replace("，", ",").split(","):
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        parts.append(normalized)
    return parts


def _join_tags(values: list[str]) -> str:
    return ",".join(values)


def _normalize_space_record(item: dict) -> dict:
    name = _normalize_text(item.get("name"))
    created_at = _normalize_text(item.get("created_at"))
    updated_at = _normalize_text(item.get("updated_at")) or created_at

    return {
        "space_id": _normalize_text(item.get("space_id")),
        "name": name,
        "tags": _join_tags(_split_tags(item.get("tags"))),
        "description": _normalize_text(item.get("description")),
        "created_at": created_at,
        "updated_at": updated_at,
    }


def list_knowledge_spaces() -> list[dict]:
    spaces: list[dict] = []

    for item in _load_raw_spaces():
        normalized = _normalize_space_record(item)
        if not normalized["space_id"] or not normalized["name"]:
            continue
        spaces.append(normalized)

    return sorted(spaces, key=lambda item: (item["name"], item["created_at"], item["space_id"]))


def get_knowledge_space(space_id: str) -> dict | None:
    normalized_space_id = _normalize_text(space_id)
    if not normalized_space_id:
        return None

    for item in list_knowledge_spaces():
        if item["space_id"] == normalized_space_id:
            return item

    return None


def create_knowledge_space(*, name: str, tags: str = "", description: str = "") -> dict:
    normalized_name = _normalize_text(name)
    normalized_tags = _join_tags(_split_tags(tags))
    normalized_description = _normalize_text(description)

    if not normalized_name:
        raise ValueError("知识库名称不能为空")

    raw_spaces = _load_raw_spaces()
    if any(_normalize_text(item.get("name")) == normalized_name for item in raw_spaces):
        raise ValueError("已存在同名知识库")

    now = datetime.now(timezone.utc).isoformat()
    space_id = str(uuid.uuid4())
    raw_spaces.append(
        {
            "space_id": space_id,
            "name": normalized_name,
            "tags": normalized_tags,
            "description": normalized_description,
            "created_at": now,
            "updated_at": now,
        }
    )
    _save_raw_spaces(raw_spaces)

    created_space = get_knowledge_space(space_id)
    if created_space is None:
        raise ValueError("知识库创建失败")

    return created_space


def update_knowledge_space(*, space_id: str, name: str, tags: str = "", description: str = "") -> dict:
    normalized_space_id = _normalize_text(space_id)
    normalized_name = _normalize_text(name)
    normalized_tags = _join_tags(_split_tags(tags))
    normalized_description = _normalize_text(description)

    if not normalized_space_id:
        raise ValueError("知识库不存在")
    if not normalized_name:
        raise ValueError("知识库名称不能为空")

    raw_spaces = _load_raw_spaces()
    target_index = -1
    for index, item in enumerate(raw_spaces):
        item_space_id = _normalize_text(item.get("space_id"))
        item_name = _normalize_text(item.get("name"))
        if item_space_id == normalized_space_id:
            target_index = index
            continue
        if item_name == normalized_name:
            raise ValueError("已存在同名知识库")

    if target_index < 0:
        raise ValueError("知识库不存在")

    raw_spaces[target_index] = {
        **raw_spaces[target_index],
        "name": normalized_name,
        "tags": normalized_tags,
        "description": normalized_description,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_raw_spaces(raw_spaces)

    updated_space = get_knowledge_space(normalized_space_id)
    if updated_space is None:
        raise ValueError("知识库更新失败")

    return updated_space


def delete_knowledge_space(space_id: str) -> list[str]:
    normalized_space_id = _normalize_text(space_id)
    if not normalized_space_id:
        raise ValueError("知识库不存在")

    raw_spaces = _load_raw_spaces()
    remaining_spaces = [
        item for item in raw_spaces if _normalize_text(item.get("space_id")) != normalized_space_id
    ]

    if len(remaining_spaces) == len(raw_spaces):
        raise ValueError("知识库不存在")

    _save_raw_spaces(remaining_spaces)
    return [normalized_space_id]