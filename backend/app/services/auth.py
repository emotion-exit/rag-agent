from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import uuid
from contextvars import ContextVar, Token
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

from app.config import settings


ROLE_ADMIN = "admin"
ROLE_USER = "user"

_current_user: ContextVar[dict[str, Any] | None] = ContextVar("current_user", default=None)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_username(value: str) -> str:
    return str(value or "").strip().lower()


def _get_connection() -> sqlite3.Connection:
    db_path = Path(settings.app_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def get_app_db_connection() -> sqlite3.Connection:
    return _get_connection()


def _hash_password(password: str, salt: str) -> str:
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        120000,
    )
    return derived.hex()


def _serialize_user(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": str(row["user_id"]),
        "username": str(row["username"]),
        "role": str(row["role"]),
        "is_active": bool(row["is_active"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def _get_user_row(connection: sqlite3.Connection, user_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT user_id, username, role, is_active, created_at, updated_at FROM users WHERE user_id = ? LIMIT 1",
        (user_id,),
    ).fetchone()


def _count_other_admins(connection: sqlite3.Connection, *, excluded_user_id: str) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS total FROM users WHERE role = ? AND is_active = 1 AND user_id != ?",
        (ROLE_ADMIN, excluded_user_id),
    ).fetchone()
    return int(row["total"] if row else 0)


def initialize_auth_db() -> None:
    with _get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                role TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS auth_tokens (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_auth_tokens_user_id
            ON auth_tokens(user_id);

            CREATE INDEX IF NOT EXISTS idx_auth_tokens_expires_at
            ON auth_tokens(expires_at);
            """
        )

        admin_username = _normalize_username(settings.default_admin_username)
        admin_password = str(settings.default_admin_password or "").strip()
        has_admin = connection.execute(
            "SELECT 1 FROM users WHERE role = ? LIMIT 1",
            (ROLE_ADMIN,),
        ).fetchone()
        if not has_admin and admin_username and admin_password:
            now = _utc_now().isoformat()
            salt = secrets.token_hex(16)
            connection.execute(
                """
                INSERT INTO users (
                    user_id, username, password_hash, password_salt, role, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    admin_username,
                    _hash_password(admin_password, salt),
                    salt,
                    ROLE_ADMIN,
                    now,
                    now,
                ),
            )
        connection.commit()


def create_user(*, username: str, password: str, role: str = ROLE_USER) -> dict[str, Any]:
    normalized_username = _normalize_username(username)
    normalized_password = str(password or "")
    normalized_role = ROLE_ADMIN if role == ROLE_ADMIN else ROLE_USER

    if len(normalized_username) < 3:
        raise ValueError("用户名至少需要 3 个字符")
    if len(normalized_password) < 6:
        raise ValueError("密码至少需要 6 个字符")

    now = _utc_now().isoformat()
    salt = secrets.token_hex(16)
    user_id = str(uuid.uuid4())

    try:
        with _get_connection() as connection:
            connection.execute(
                """
                INSERT INTO users (
                    user_id, username, password_hash, password_salt, role, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    user_id,
                    normalized_username,
                    _hash_password(normalized_password, salt),
                    salt,
                    normalized_role,
                    now,
                    now,
                ),
            )
            connection.commit()
            row = connection.execute(
                "SELECT user_id, username, role, is_active, created_at, updated_at FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
    except sqlite3.IntegrityError as exc:
        raise ValueError("用户名已存在") from exc

    if row is None:
        raise ValueError("用户创建失败")

    return _serialize_user(row)


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    normalized_username = _normalize_username(username)
    normalized_password = str(password or "")
    if not normalized_username or not normalized_password:
        return None

    with _get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE username = ? LIMIT 1",
            (normalized_username,),
        ).fetchone()

    if row is None or not bool(row["is_active"]):
        return None

    expected_hash = _hash_password(normalized_password, str(row["password_salt"]))
    if not hmac.compare_digest(expected_hash, str(row["password_hash"])):
        return None

    return _serialize_user(row)


def create_auth_token(user_id: str) -> dict[str, Any]:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        raise ValueError("用户不存在")

    now = _utc_now()
    expires_at = now + timedelta(hours=max(int(settings.auth_token_ttl_hours), 1))
    token = secrets.token_urlsafe(32)

    with _get_connection() as connection:
        connection.execute(
            "INSERT INTO auth_tokens (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, normalized_user_id, now.isoformat(), expires_at.isoformat()),
        )
        connection.commit()

    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
    }


def revoke_auth_token(token: str) -> None:
    normalized_token = str(token or "").strip()
    if not normalized_token:
        return

    with _get_connection() as connection:
        connection.execute("DELETE FROM auth_tokens WHERE token = ?", (normalized_token,))
        connection.commit()


def get_user_by_token(token: str) -> dict[str, Any] | None:
    normalized_token = str(token or "").strip()
    if not normalized_token:
        return None

    now = _utc_now().isoformat()
    with _get_connection() as connection:
        connection.execute("DELETE FROM auth_tokens WHERE expires_at <= ?", (now,))
        row = connection.execute(
            """
            SELECT users.user_id, users.username, users.role, users.is_active, users.created_at, users.updated_at
            FROM auth_tokens
            INNER JOIN users ON users.user_id = auth_tokens.user_id
            WHERE auth_tokens.token = ? AND auth_tokens.expires_at > ?
            LIMIT 1
            """,
            (normalized_token, now),
        ).fetchone()
        connection.commit()

    if row is None or not bool(row["is_active"]):
        return None

    return _serialize_user(row)


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        return None

    with _get_connection() as connection:
        row = connection.execute(
            "SELECT user_id, username, role, is_active, created_at, updated_at FROM users WHERE user_id = ? LIMIT 1",
            (normalized_user_id,),
        ).fetchone()

    if row is None:
        return None

    return _serialize_user(row)


def count_users() -> int:
    with _get_connection() as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()
    return int(row["total"] if row else 0)


def list_users() -> list[dict[str, Any]]:
    with _get_connection() as connection:
        rows = connection.execute(
            """
            SELECT user_id, username, role, is_active, created_at, updated_at
            FROM users
            ORDER BY CASE WHEN role = ? THEN 0 ELSE 1 END, created_at ASC, username ASC
            """,
            (ROLE_ADMIN,),
        ).fetchall()
    return [_serialize_user(row) for row in rows]


def update_user_password(*, user_id: str, password: str) -> dict[str, Any]:
    normalized_user_id = str(user_id or "").strip()
    normalized_password = str(password or "")
    if not normalized_user_id:
        raise ValueError("用户不存在")
    if len(normalized_password) < 6:
        raise ValueError("密码至少需要 6 个字符")

    salt = secrets.token_hex(16)
    now = _utc_now().isoformat()
    with _get_connection() as connection:
        row = _get_user_row(connection, normalized_user_id)
        if row is None:
            raise ValueError("用户不存在")

        connection.execute(
            """
            UPDATE users
            SET password_hash = ?, password_salt = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (
                _hash_password(normalized_password, salt),
                salt,
                now,
                normalized_user_id,
            ),
        )
        connection.execute("DELETE FROM auth_tokens WHERE user_id = ?", (normalized_user_id,))
        connection.commit()
        updated_row = _get_user_row(connection, normalized_user_id)

    if updated_row is None:
        raise ValueError("用户不存在")
    return _serialize_user(updated_row)


def update_user_role(*, user_id: str, role: str, actor_user_id: str | None = None) -> dict[str, Any]:
    normalized_user_id = str(user_id or "").strip()
    normalized_role = ROLE_ADMIN if role == ROLE_ADMIN else ROLE_USER
    normalized_actor_user_id = str(actor_user_id or "").strip()
    if not normalized_user_id:
        raise ValueError("用户不存在")

    now = _utc_now().isoformat()
    with _get_connection() as connection:
        row = _get_user_row(connection, normalized_user_id)
        if row is None:
            raise ValueError("用户不存在")

        current_role = str(row["role"])
        if current_role == ROLE_ADMIN and normalized_role != ROLE_ADMIN:
            if normalized_actor_user_id and normalized_user_id == normalized_actor_user_id:
                raise ValueError("不能移除自己的管理员角色")
            if _count_other_admins(connection, excluded_user_id=normalized_user_id) <= 0:
                raise ValueError("至少需要保留一个启用中的管理员账号")

        connection.execute(
            "UPDATE users SET role = ?, updated_at = ? WHERE user_id = ?",
            (normalized_role, now, normalized_user_id),
        )
        connection.commit()
        updated_row = _get_user_row(connection, normalized_user_id)

    if updated_row is None:
        raise ValueError("用户不存在")
    return _serialize_user(updated_row)


def update_user_active_status(
    *,
    user_id: str,
    is_active: bool,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    normalized_user_id = str(user_id or "").strip()
    normalized_actor_user_id = str(actor_user_id or "").strip()
    if not normalized_user_id:
        raise ValueError("用户不存在")

    next_is_active = 1 if is_active else 0
    now = _utc_now().isoformat()
    with _get_connection() as connection:
        row = connection.execute(
            "SELECT user_id, username, role, is_active, created_at, updated_at FROM users WHERE user_id = ? LIMIT 1",
            (normalized_user_id,),
        ).fetchone()
        if row is None:
            raise ValueError("用户不存在")

        current_role = str(row["role"])
        current_is_active = int(row["is_active"] or 0)
        if current_is_active == next_is_active:
            return _serialize_user(row)

        if next_is_active == 0 and current_role == ROLE_ADMIN:
            if normalized_actor_user_id and normalized_user_id == normalized_actor_user_id:
                raise ValueError("不能停用当前管理员账号")
            if _count_other_admins(connection, excluded_user_id=normalized_user_id) <= 0:
                raise ValueError("至少需要保留一个启用中的管理员账号")

        connection.execute(
            "UPDATE users SET is_active = ?, updated_at = ? WHERE user_id = ?",
            (next_is_active, now, normalized_user_id),
        )
        if next_is_active == 0:
            connection.execute("DELETE FROM auth_tokens WHERE user_id = ?", (normalized_user_id,))
        connection.commit()
        updated_row = _get_user_row(connection, normalized_user_id)

    if updated_row is None:
        raise ValueError("用户不存在")
    return _serialize_user(updated_row)


def set_current_user(user: dict[str, Any] | None) -> Token[dict[str, Any] | None]:
    return _current_user.set(user)


def reset_current_user(token: Token[dict[str, Any] | None]) -> None:
    _current_user.reset(token)


def get_current_user(required: bool = True) -> dict[str, Any] | None:
    user = _current_user.get()
    if user is None and required:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def is_admin(user: dict[str, Any] | None) -> bool:
    return bool(user) and str(user.get("role", "")) == ROLE_ADMIN


def extract_token_from_request(request: Request) -> str:
    auth_header = str(request.headers.get("authorization", "") or "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    header_token = str(request.headers.get("x-auth-token", "") or "").strip()
    if header_token:
        return header_token
    return str(request.query_params.get("auth_token", "") or "").strip()


def get_request_user(request: Request) -> dict[str, Any] | None:
    user = getattr(request.state, "current_user", None)
    if isinstance(user, dict):
        return user
    return None