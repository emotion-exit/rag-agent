from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.auth.database import get_connection
from app.config import (
    diff_public_frontend_config,
    get_public_frontend_config_seed,
    merge_public_frontend_config,
    normalize_public_frontend_config,
)


SYSTEM_PUBLIC_CONFIG_KEY = "default"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _filter_allowed_fields(
    payload: dict[str, Any] | None,
    allowed_fields: set[str] | None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    if allowed_fields is None:
        return dict(payload)
    return {key: value for key, value in payload.items() if key in allowed_fields}


def initialize_public_config_db() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS system_public_configs (
                config_key TEXT PRIMARY KEY,
                config_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_public_configs (
                user_id TEXT PRIMARY KEY,
                config_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )
        _ensure_system_public_config(connection)


def _ensure_system_public_config(connection) -> dict[str, Any]:
    row = connection.execute(
        "SELECT config_json FROM system_public_configs WHERE config_key = ? LIMIT 1",
        (SYSTEM_PUBLIC_CONFIG_KEY,),
    ).fetchone()
    if row is not None:
        raw_config = str(row["config_json"] or "").strip()
        if raw_config:
            try:
                payload = json.loads(raw_config)
                if isinstance(payload, dict):
                    return normalize_public_frontend_config(payload)
            except json.JSONDecodeError:
                pass

    defaults = get_public_frontend_config_seed()
    now = _utc_now_iso()
    connection.execute(
        """
        INSERT INTO system_public_configs (config_key, config_json, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(config_key) DO UPDATE SET
            config_json = excluded.config_json,
            updated_at = excluded.updated_at
        """,
        (
            SYSTEM_PUBLIC_CONFIG_KEY,
            json.dumps(defaults, ensure_ascii=False),
            now,
            now,
        ),
    )
    return defaults


def _load_user_overrides(connection, user_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT config_json FROM user_public_configs WHERE user_id = ? LIMIT 1",
        (str(user_id or "").strip(),),
    ).fetchone()
    if row is None:
        return None

    raw_config = str(row["config_json"] or "").strip()
    if not raw_config:
        return {}
    try:
        payload = json.loads(raw_config)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def get_system_public_config() -> dict[str, Any]:
    with get_connection() as connection:
        return _ensure_system_public_config(connection)


def save_system_public_config(source: dict[str, Any] | None) -> dict[str, Any]:
    normalized = normalize_public_frontend_config(source)
    now = _utc_now_iso()
    with get_connection() as connection:
        _ensure_system_public_config(connection)
        connection.execute(
            """
            INSERT INTO system_public_configs (config_key, config_json, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(config_key) DO UPDATE SET
                config_json = excluded.config_json,
                updated_at = excluded.updated_at
            """,
            (
                SYSTEM_PUBLIC_CONFIG_KEY,
                json.dumps(normalized, ensure_ascii=False),
                now,
                now,
            ),
        )
    return normalized


def reset_system_public_config() -> dict[str, Any]:
    defaults = get_public_frontend_config_seed()
    return save_system_public_config(defaults)


def get_user_public_config_overrides(
    user_id: str,
    *,
    allowed_fields: set[str] | None = None,
) -> dict[str, Any]:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        return {}

    with get_connection() as connection:
        system_config = _ensure_system_public_config(connection)
        overrides = _filter_allowed_fields(_load_user_overrides(connection, normalized_user_id), allowed_fields)
    return diff_public_frontend_config(overrides, system_config) if overrides is not None else {}


def get_user_public_config(
    user_id: str,
    *,
    allowed_fields: set[str] | None = None,
) -> dict[str, Any]:
    normalized_user_id = str(user_id or "").strip()
    system_config = get_system_public_config()
    if not normalized_user_id:
        return system_config

    with get_connection() as connection:
        _ensure_system_public_config(connection)
        overrides = _filter_allowed_fields(_load_user_overrides(connection, normalized_user_id), allowed_fields)
    return merge_public_frontend_config(system_config, overrides)


def save_user_public_config(
    user_id: str,
    source: dict[str, Any] | None,
    *,
    allowed_fields: set[str] | None = None,
) -> dict[str, Any]:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        raise ValueError("用户不存在")

    now = _utc_now_iso()
    with get_connection() as connection:
        system_config = _ensure_system_public_config(connection)
        effective_config = normalize_public_frontend_config(
            source,
            fallback=system_config,
            allowed_fields=allowed_fields,
        )
        overrides = diff_public_frontend_config(effective_config, system_config)
        connection.execute(
            """
            INSERT INTO user_public_configs (user_id, config_json, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                config_json = excluded.config_json,
                updated_at = excluded.updated_at
            """,
            (
                normalized_user_id,
                json.dumps(overrides, ensure_ascii=False),
                now,
                now,
            ),
        )
    return effective_config


def reset_user_public_config(user_id: str) -> dict[str, Any]:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        raise ValueError("用户不存在")

    with get_connection() as connection:
        system_config = _ensure_system_public_config(connection)
        connection.execute("DELETE FROM user_public_configs WHERE user_id = ?", (normalized_user_id,))
    return system_config