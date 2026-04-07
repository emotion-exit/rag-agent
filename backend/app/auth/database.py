"""认证相关的 SQLite 存储。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config import settings


def _database_path() -> Path:
    return Path(settings.auth_db_path)


def ensure_auth_storage_ready() -> None:
    database_path = _database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    ensure_auth_storage_ready()
    connection = sqlite3.connect(_database_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_auth_database() -> None:
    ensure_auth_storage_ready()
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                primary_auth_method TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_identities (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                app_id TEXT NOT NULL DEFAULT '',
                openid TEXT NOT NULL DEFAULT '',
                unionid TEXT NOT NULL DEFAULT '',
                nickname_snapshot TEXT NOT NULL DEFAULT '',
                avatar_url_snapshot TEXT NOT NULL DEFAULT '',
                bound_at TEXT NOT NULL,
                last_login_at TEXT NOT NULL,
                unbound_at TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_user_identities_user_id
            ON user_identities(user_id);

            CREATE INDEX IF NOT EXISTS idx_user_identities_provider_openid
            ON user_identities(provider, app_id, openid);

            CREATE INDEX IF NOT EXISTS idx_user_identities_provider_unionid
            ON user_identities(provider, unionid);

            CREATE UNIQUE INDEX IF NOT EXISTS uq_user_identities_provider_unionid_active
            ON user_identities(provider, unionid)
            WHERE unionid != '' AND status = 'active';

            CREATE UNIQUE INDEX IF NOT EXISTS uq_user_identities_provider_app_openid_active
            ON user_identities(provider, app_id, openid)
            WHERE app_id != '' AND openid != '' AND status = 'active';
            """
        )