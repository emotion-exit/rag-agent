import sqlite3
import uuid
from datetime import datetime, timezone

from app.services.auth import get_app_db_connection, is_admin


VISIBILITY_PUBLIC = "public"
VISIBILITY_PRIVATE = "private"


def _get_connection() -> sqlite3.Connection:
    return get_app_db_connection()


def _owner_id_column_requires_migration(connection: sqlite3.Connection) -> bool:
    rows = connection.execute("PRAGMA table_info(knowledge_spaces)").fetchall()
    for row in rows:
        if str(row["name"]) != "owner_id":
            continue
        not_null = int(row["notnull"] or 0)
        default_value = str(row["dflt_value"] or "").strip()
        return not_null == 1 or default_value in {"''", '""'}
    return False


def _migrate_knowledge_spaces_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        ALTER TABLE knowledge_spaces RENAME TO knowledge_spaces_legacy;

        CREATE TABLE knowledge_spaces (
            space_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            owner_id TEXT,
            visibility TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(owner_id) REFERENCES users(user_id) ON DELETE SET NULL
        );

        INSERT INTO knowledge_spaces (
            space_id, name, tags, description, owner_id, visibility, created_at, updated_at
        )
        SELECT
            space_id,
            name,
            tags,
            description,
            NULLIF(owner_id, ''),
            visibility,
            created_at,
            updated_at
        FROM knowledge_spaces_legacy;

        DROP TABLE knowledge_spaces_legacy;

        CREATE INDEX IF NOT EXISTS idx_knowledge_spaces_visibility
        ON knowledge_spaces(visibility);

        CREATE INDEX IF NOT EXISTS idx_knowledge_spaces_owner_id
        ON knowledge_spaces(owner_id);

        CREATE INDEX IF NOT EXISTS idx_knowledge_spaces_name_visibility_owner
        ON knowledge_spaces(name, visibility, owner_id);
        """
    )


def initialize_knowledge_space_db() -> None:
    with _get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS knowledge_spaces (
                space_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                owner_id TEXT,
                visibility TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(owner_id) REFERENCES users(user_id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_knowledge_spaces_visibility
            ON knowledge_spaces(visibility);

            CREATE INDEX IF NOT EXISTS idx_knowledge_spaces_owner_id
            ON knowledge_spaces(owner_id);

            CREATE INDEX IF NOT EXISTS idx_knowledge_spaces_name_visibility_owner
            ON knowledge_spaces(name, visibility, owner_id);
            """
        )

        if _owner_id_column_requires_migration(connection):
            _migrate_knowledge_spaces_schema(connection)

        row = connection.execute(
            "SELECT COUNT(*) AS total FROM knowledge_spaces"
        ).fetchone()
        connection.commit()


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
    visibility = _normalize_text(item.get("visibility")) or VISIBILITY_PUBLIC

    return {
        "space_id": _normalize_text(item.get("space_id")),
        "name": name,
        "tags": _join_tags(_split_tags(item.get("tags"))),
        "description": _normalize_text(item.get("description")),
        "owner_id": _normalize_text(item.get("owner_id")),
        "visibility": visibility if visibility in (VISIBILITY_PUBLIC, VISIBILITY_PRIVATE) else VISIBILITY_PUBLIC,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def can_read_space(space: dict, user: dict | None) -> bool:
    visibility = _normalize_text(space.get("visibility")) or VISIBILITY_PUBLIC
    if visibility == VISIBILITY_PUBLIC:
        return user is not None
    if user is None:
        return False
    owner_id = _normalize_text(space.get("owner_id"))
    return is_admin(user) or owner_id == _normalize_text(user.get("user_id"))


def can_manage_space(space: dict, user: dict | None) -> bool:
    if user is None:
        return False
    visibility = _normalize_text(space.get("visibility")) or VISIBILITY_PUBLIC
    owner_id = _normalize_text(space.get("owner_id"))
    if visibility == VISIBILITY_PUBLIC:
        return is_admin(user)
    return is_admin(user) or owner_id == _normalize_text(user.get("user_id"))


def list_knowledge_spaces(user: dict | None = None) -> list[dict]:
    initialize_knowledge_space_db()
    spaces: list[dict] = []

    with _get_connection() as connection:
        rows = connection.execute(
            """
            SELECT space_id, name, tags, description, owner_id, visibility, created_at, updated_at
            FROM knowledge_spaces
            """
        ).fetchall()

    for row in rows:
        normalized = _normalize_space_record(dict(row))
        if not normalized["space_id"] or not normalized["name"]:
            continue
        if user is not None and not can_read_space(normalized, user):
            continue
        spaces.append(normalized)

    return sorted(spaces, key=lambda item: (item["name"], item["created_at"], item["space_id"]))


def list_accessible_space_ids(user: dict | None) -> list[str]:
    if user is None:
        return []
    return [item["space_id"] for item in list_knowledge_spaces(user)]


def get_knowledge_space(space_id: str, user: dict | None = None) -> dict | None:
    normalized_space_id = _normalize_text(space_id)
    if not normalized_space_id:
        return None

    for item in list_knowledge_spaces(user):
        if item["space_id"] == normalized_space_id:
            return item

    return None


def _is_duplicate_name(raw_spaces: list[dict], *, name: str, visibility: str, owner_id: str, current_space_id: str = "") -> bool:
    for item in raw_spaces:
        item_name = _normalize_text(item.get("name"))
        item_visibility = _normalize_text(item.get("visibility")) or VISIBILITY_PUBLIC
        item_owner_id = _normalize_text(item.get("owner_id"))
        item_space_id = _normalize_text(item.get("space_id"))
        if current_space_id and item_space_id == current_space_id:
            continue
        if item_name != name or item_visibility != visibility:
            continue
        if visibility == VISIBILITY_PUBLIC:
            return True
        if item_owner_id == owner_id:
            return True
    return False


def create_knowledge_space(
    *,
    name: str,
    tags: str = "",
    description: str = "",
    owner_id: str = "",
    visibility: str = VISIBILITY_PRIVATE,
) -> dict:
    initialize_knowledge_space_db()
    normalized_name = _normalize_text(name)
    normalized_tags = _join_tags(_split_tags(tags))
    normalized_description = _normalize_text(description)
    normalized_owner_id = _normalize_text(owner_id)
    normalized_visibility = _normalize_text(visibility) or VISIBILITY_PRIVATE
    db_owner_id = normalized_owner_id or None

    if not normalized_name:
        raise ValueError("知识库名称不能为空")
    if normalized_visibility not in (VISIBILITY_PUBLIC, VISIBILITY_PRIVATE):
        raise ValueError("知识库可见性不合法")
    if normalized_visibility == VISIBILITY_PRIVATE and not normalized_owner_id:
        raise ValueError("私有知识库必须绑定所属用户")

    now = datetime.now(timezone.utc).isoformat()
    space_id = str(uuid.uuid4())

    with _get_connection() as connection:
        rows = connection.execute(
            """
            SELECT space_id, name, owner_id, visibility
            FROM knowledge_spaces
            """
        ).fetchall()
        raw_spaces = [dict(row) for row in rows]
        if _is_duplicate_name(
            raw_spaces,
            name=normalized_name,
            visibility=normalized_visibility,
            owner_id=normalized_owner_id,
        ):
            raise ValueError("已存在同名知识库")

        connection.execute(
            """
            INSERT INTO knowledge_spaces (
                space_id, name, tags, description, owner_id, visibility, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                space_id,
                normalized_name,
                normalized_tags,
                normalized_description,
                db_owner_id,
                normalized_visibility,
                now,
                now,
            ),
        )
        connection.commit()

    created_space = get_knowledge_space(space_id, None)
    if created_space is None:
        raise ValueError("知识库创建失败")

    return created_space


def update_knowledge_space(
    *,
    space_id: str,
    name: str,
    tags: str = "",
    description: str = "",
    visibility: str = VISIBILITY_PRIVATE,
) -> dict:
    initialize_knowledge_space_db()
    normalized_space_id = _normalize_text(space_id)
    normalized_name = _normalize_text(name)
    normalized_tags = _join_tags(_split_tags(tags))
    normalized_description = _normalize_text(description)
    normalized_visibility = _normalize_text(visibility) or VISIBILITY_PRIVATE

    if not normalized_space_id:
        raise ValueError("知识库不存在")
    if not normalized_name:
        raise ValueError("知识库名称不能为空")
    if normalized_visibility not in (VISIBILITY_PUBLIC, VISIBILITY_PRIVATE):
        raise ValueError("知识库可见性不合法")

    with _get_connection() as connection:
        rows = connection.execute(
            """
            SELECT space_id, name, owner_id, visibility
            FROM knowledge_spaces
            """
        ).fetchall()
        raw_spaces = [dict(row) for row in rows]

        target_owner_id = ""
        target_exists = False
        for item in raw_spaces:
            item_space_id = _normalize_text(item.get("space_id"))
            if item_space_id != normalized_space_id:
                continue
            target_exists = True
            target_owner_id = _normalize_text(item.get("owner_id"))
            break

        if not target_exists:
            raise ValueError("知识库不存在")
        if normalized_visibility == VISIBILITY_PRIVATE and not target_owner_id:
            raise ValueError("私有知识库必须绑定所属用户")
        if _is_duplicate_name(
            raw_spaces,
            name=normalized_name,
            visibility=normalized_visibility,
            owner_id=target_owner_id,
            current_space_id=normalized_space_id,
        ):
            raise ValueError("已存在同名知识库")

        connection.execute(
            """
            UPDATE knowledge_spaces
            SET name = ?, tags = ?, description = ?, visibility = ?, updated_at = ?
            WHERE space_id = ?
            """,
            (
                normalized_name,
                normalized_tags,
                normalized_description,
                normalized_visibility,
                datetime.now(timezone.utc).isoformat(),
                normalized_space_id,
            ),
        )
        connection.commit()

    updated_space = get_knowledge_space(normalized_space_id, None)
    if updated_space is None:
        raise ValueError("知识库更新失败")

    return updated_space


def delete_knowledge_space(space_id: str) -> list[str]:
    initialize_knowledge_space_db()
    normalized_space_id = _normalize_text(space_id)
    if not normalized_space_id:
        raise ValueError("知识库不存在")

    with _get_connection() as connection:
        row = connection.execute(
            "SELECT 1 FROM knowledge_spaces WHERE space_id = ? LIMIT 1",
            (normalized_space_id,),
        ).fetchone()
        if row is None:
            raise ValueError("知识库不存在")

        connection.execute(
            "DELETE FROM knowledge_spaces WHERE space_id = ?",
            (normalized_space_id,),
        )
        connection.commit()

    return [normalized_space_id]