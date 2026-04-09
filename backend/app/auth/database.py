"""认证相关的 SQLite 存储。"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from app.config import settings


def _database_path() -> Path:
    return Path(settings.auth_db_path)


def ensure_auth_storage_ready() -> None:
    database_path = _database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_username(value: str | None) -> str:
    return str(value or "").strip().lower()


def _hash_password(password: str, salt: str) -> str:
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        str(password or "").encode("utf-8"),
        bytes.fromhex(salt),
        120000,
    )
    return derived.hex()


def _has_column(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row[1]) == column_name for row in rows)


def _ensure_users_schema(connection: sqlite3.Connection) -> None:
    if not _has_column(connection, "users", "username"):
        connection.execute("ALTER TABLE users ADD COLUMN username TEXT NOT NULL DEFAULT ''")
    if not _has_column(connection, "users", "password_hash"):
        connection.execute("ALTER TABLE users ADD COLUMN password_hash TEXT NOT NULL DEFAULT ''")
    if not _has_column(connection, "users", "password_salt"):
        connection.execute("ALTER TABLE users ADD COLUMN password_salt TEXT NOT NULL DEFAULT ''")
    if not _has_column(connection, "users", "role"):
        connection.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    if not _has_column(connection, "users", "is_active"):
        connection.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")

    connection.execute("UPDATE users SET username = COALESCE(username, '')")
    connection.execute("UPDATE users SET password_hash = COALESCE(password_hash, '')")
    connection.execute("UPDATE users SET password_salt = COALESCE(password_salt, '')")
    connection.execute("UPDATE users SET role = CASE WHEN COALESCE(role, '') = '' THEN 'user' ELSE role END")
    connection.execute("UPDATE users SET is_active = COALESCE(is_active, 1)")

    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username_non_empty ON users(username) WHERE username != ''"
    )


def _ensure_auth_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL DEFAULT '',
            password_hash TEXT NOT NULL DEFAULT '',
            password_salt TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT 'user',
            is_active INTEGER NOT NULL DEFAULT 1,
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

        CREATE TABLE IF NOT EXISTS auth_token_revocations (
            token TEXT PRIMARY KEY,
            revoked_at TEXT NOT NULL,
            expires_at TEXT
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
    _ensure_users_schema(connection)


def _ensure_default_admin(connection: sqlite3.Connection) -> None:
    admin_row = connection.execute(
        "SELECT 1 FROM users WHERE role = 'admin' AND is_active = 1 LIMIT 1"
    ).fetchone()
    if admin_row is not None:
        return

    username = _normalize_username(settings.default_admin_username)
    password = str(settings.default_admin_password or "").strip()
    if len(username) < 3 or len(password) < 6:
        return

    now = _utc_now_iso()
    salt = secrets.token_hex(16)
    connection.execute(
        """
        INSERT OR IGNORE INTO users (
            id, username, password_hash, password_salt, role, is_active,
            primary_auth_method, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'admin', 1, 'password', 'active', ?, ?)
        """,
        (
            str(uuid4()),
            username,
            _hash_password(password, salt),
            salt,
            now,
            now,
        ),
    )


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
        _ensure_auth_schema(connection)
        _ensure_default_admin(connection)