from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.config import (
    diff_public_frontend_config,
    get_public_frontend_config_seed,
    merge_public_frontend_config,
    normalize_public_frontend_config,
)
from app.services.auth import get_app_db_connection


SYSTEM_PUBLIC_CONFIG_KEY = "default"


def _filter_allowed_public_config_fields(
    source: dict[str, Any] | None,
    allowed_fields: set[str] | None,
) -> dict[str, Any]:
    if not isinstance(source, dict):
        return {}

    if not allowed_fields:
        return dict(source)

    return {
        key: value
        for key, value in source.items()
        if key in allowed_fields
    }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def initialize_public_config_db() -> None:
    with get_app_db_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS system_public_configs (
                config_key TEXT PRIMARY KEY,
                config_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_system_public_configs_updated_at
            ON system_public_configs(updated_at DESC);

            CREATE TABLE IF NOT EXISTS user_public_configs (
                user_id TEXT PRIMARY KEY,
                config_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_user_public_configs_updated_at
            ON user_public_configs(updated_at DESC);
            """
        )
        _ensure_system_public_config(connection)
        connection.commit()


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
    now = _utc_now().isoformat()
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


def get_system_public_config() -> dict[str, Any]:
    with get_app_db_connection() as connection:
        config = _ensure_system_public_config(connection)
        connection.commit()
    return config


def _load_user_public_config_row(connection, user_id: str) -> dict[str, Any] | None:
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


def get_user_public_config_overrides(
    user_id: str,
    *,
    allowed_fields: set[str] | None = None,
) -> dict[str, Any]:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        return {}

    with get_app_db_connection() as connection:
        system_config = _ensure_system_public_config(connection)
        raw_overrides = _load_user_public_config_row(connection, normalized_user_id)
        connection.commit()

    raw_overrides = _filter_allowed_public_config_fields(raw_overrides, allowed_fields)
    return diff_public_frontend_config(raw_overrides, system_config) if raw_overrides is not None else {}


def get_user_public_config(
    user_id: str,
    *,
    allowed_fields: set[str] | None = None,
) -> dict[str, Any]:
    normalized_user_id = str(user_id or "").strip()
    system_config = get_system_public_config()
    if not normalized_user_id:
        return system_config

    with get_app_db_connection() as connection:
        system_config = _ensure_system_public_config(connection)
        raw_overrides = _load_user_public_config_row(connection, normalized_user_id)
        connection.commit()

    raw_overrides = _filter_allowed_public_config_fields(raw_overrides, allowed_fields)
    return merge_public_frontend_config(system_config, raw_overrides)


def save_user_public_config(
    user_id: str,
    source: dict[str, Any] | None,
    *,
    allowed_fields: set[str] | None = None,
) -> dict[str, Any]:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        raise ValueError("用户不存在")

    now = _utc_now().isoformat()
    with get_app_db_connection() as connection:
        system_config = _ensure_system_public_config(connection)
        normalized_effective_config = normalize_public_frontend_config(
            source,
            fallback=system_config,
            allowed_fields=allowed_fields,
        )
        stored_overrides = diff_public_frontend_config(normalized_effective_config, system_config)

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
                json.dumps(stored_overrides, ensure_ascii=False),
                now,
                now,
            ),
        )
        connection.commit()

    return normalized_effective_config


def reset_user_public_config(user_id: str) -> dict[str, Any]:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        raise ValueError("用户不存在")

    with get_app_db_connection() as connection:
        system_config = _ensure_system_public_config(connection)
        connection.execute(
            "DELETE FROM user_public_configs WHERE user_id = ?",
            (normalized_user_id,),
        )
        connection.commit()

    return system_config


def save_system_public_config(source: dict[str, Any] | None) -> dict[str, Any]:
    normalized_config = normalize_public_frontend_config(source)
    now = _utc_now().isoformat()

    with get_app_db_connection() as connection:
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
                json.dumps(normalized_config, ensure_ascii=False),
                now,
                now,
            ),
        )
        connection.commit()

    return normalized_config


def reset_system_public_config() -> dict[str, Any]:
    defaults = get_public_frontend_config_seed()
    now = _utc_now().isoformat()
    with get_app_db_connection() as connection:
        _ensure_system_public_config(connection)
        connection.execute(
            """
            UPDATE system_public_configs
            SET config_json = ?, updated_at = ?
            WHERE config_key = ?
            """,
            (
                json.dumps(defaults, ensure_ascii=False),
                now,
                SYSTEM_PUBLIC_CONFIG_KEY,
            ),
        )
        connection.commit()

    return defaults