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

    parts = []
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


def _build_space_path(space_id: str, lookup: dict[str, dict]) -> str:
    current = lookup.get(space_id)
    segments: list[str] = []

    while current:
      segments.append(str(current.get("name", "")).strip())
      parent_id = str(current.get("parent_id", "")).strip()
      current = lookup.get(parent_id) if parent_id else None

    return " / ".join(reversed([segment for segment in segments if segment]))


def list_knowledge_spaces() -> list[dict]:
    raw_spaces = _load_raw_spaces()
    lookup = {
        str(item.get("space_id", "")).strip(): item
        for item in raw_spaces
        if str(item.get("space_id", "")).strip()
    }

    spaces: list[dict] = []
    for item in raw_spaces:
        space_id = str(item.get("space_id", "")).strip()
        if not space_id:
            continue

        parent_id = str(item.get("parent_id", "")).strip()
        path = _build_space_path(space_id, lookup)
        spaces.append(
            {
                "space_id": space_id,
                "name": _normalize_text(item.get("name")),
                "parent_id": parent_id,
                "category": _normalize_text(item.get("category")),
                "topic": _normalize_text(item.get("topic")),
                "tags": _normalize_text(item.get("tags")),
                "version_label": _normalize_text(item.get("version_label")),
                "description": _normalize_text(item.get("description")),
                "created_at": _normalize_text(item.get("created_at")),
                "path": path,
                "depth": path.count(" / "),
            }
        )

    return sorted(spaces, key=lambda item: (item["path"], item["created_at"], item["space_id"]))


def get_knowledge_space(space_id: str) -> dict | None:
    normalized_space_id = _normalize_text(space_id)
    if not normalized_space_id:
        return None

    for item in list_knowledge_spaces():
        if item["space_id"] == normalized_space_id:
            return item

    return None


def create_knowledge_space(
    *,
    name: str,
    parent_id: str = "",
    category: str,
    topic: str,
    tags: str = "",
    version_label: str = "",
    description: str = "",
) -> dict:
    normalized_name = _normalize_text(name)
    normalized_parent_id = _normalize_text(parent_id)
    normalized_category = _normalize_text(category)
    normalized_topic = _normalize_text(topic)
    normalized_tags = _join_tags(_split_tags(tags))
    normalized_version_label = _normalize_text(version_label)
    normalized_description = _normalize_text(description)

    if not normalized_name:
        raise ValueError("知识空间名称不能为空")
    if not normalized_category:
        raise ValueError("分类不能为空")
    if not normalized_topic:
        raise ValueError("主题不能为空")

    raw_spaces = _load_raw_spaces()
    if normalized_parent_id and not any(
        _normalize_text(item.get("space_id")) == normalized_parent_id
        for item in raw_spaces
    ):
        raise ValueError("父级知识空间不存在")

    for item in raw_spaces:
        sibling_parent_id = _normalize_text(item.get("parent_id"))
        sibling_name = _normalize_text(item.get("name"))
        if sibling_parent_id == normalized_parent_id and sibling_name == normalized_name:
            raise ValueError("同一级下已存在同名知识空间")

    space_id = str(uuid.uuid4())
    raw_spaces.append(
        {
            "space_id": space_id,
            "name": normalized_name,
            "parent_id": normalized_parent_id,
            "category": normalized_category,
            "topic": normalized_topic,
            "tags": normalized_tags,
            "version_label": normalized_version_label,
            "description": normalized_description,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    _save_raw_spaces(raw_spaces)

    created_space = get_knowledge_space(space_id)
    if created_space is None:
        raise ValueError("知识空间创建失败")

    return created_space