"""认证与微信身份登录服务。"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.auth.database import get_connection


AUTH_PROVIDER_WECHAT = "wechat"
AUTH_METHOD_PASSWORD = "password"
IDENTITY_STATUS_ACTIVE = "active"
IDENTITY_STATUS_UNBOUND = "unbound"
USER_STATUS_ACTIVE = "active"
ROLE_ADMIN = "admin"
ROLE_USER = "user"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: str | None) -> str:
    return str(value or "").strip()


def _normalize_username(value: str | None) -> str:
    return _normalize_text(value).lower()


def _hash_password(password: str, salt: str) -> str:
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        str(password or "").encode("utf-8"),
        bytes.fromhex(salt),
        120000,
    )
    return derived.hex()


def _has_column(connection: Any, table_name: str, column_name: str) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row[1]) == column_name for row in rows)


def _ensure_legacy_user_columns(connection: Any) -> None:
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


def _ensure_auth_schema(connection: Any) -> None:
    _ensure_legacy_user_columns(connection)


def _normalize_identity_payload(payload: dict[str, Any]) -> dict[str, str]:
    provider = _normalize_text(payload.get("provider") or AUTH_PROVIDER_WECHAT) or AUTH_PROVIDER_WECHAT
    app_id = _normalize_text(payload.get("app_id"))
    openid = _normalize_text(payload.get("openid"))
    unionid = _normalize_text(payload.get("unionid"))
    nickname = _normalize_text(payload.get("nickname"))
    avatar_url = _normalize_text(payload.get("avatar_url"))

    if not unionid and not openid:
        raise HTTPException(status_code=400, detail="微信登录至少需要提供 unionid 或 openid")
    if openid and not app_id:
        raise HTTPException(status_code=400, detail="提供 openid 时必须同时提供 app_id")

    return {
        "provider": provider,
        "app_id": app_id,
        "openid": openid,
        "unionid": unionid,
        "nickname": nickname,
        "avatar_url": avatar_url,
    }


def _row_to_user(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "primary_auth_method": row["primary_auth_method"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_identity(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "provider": row["provider"],
        "app_id": row["app_id"],
        "openid": row["openid"],
        "unionid": row["unionid"],
        "nickname_snapshot": row["nickname_snapshot"],
        "avatar_url_snapshot": row["avatar_url_snapshot"],
        "bound_at": row["bound_at"],
        "last_login_at": row["last_login_at"],
        "unbound_at": row["unbound_at"],
        "status": row["status"],
    }


def _get_user_by_id(connection: Any, user_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT id, username, role, is_active, primary_auth_method, status, created_at, updated_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        _ensure_auth_schema(connection)
        return _get_user_by_id(connection, user_id)


def _list_user_identities(connection: Any, user_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT id, user_id, provider, app_id, openid, unionid, nickname_snapshot,
               avatar_url_snapshot, bound_at, last_login_at, unbound_at, status
        FROM user_identities
        WHERE user_id = ?
        ORDER BY bound_at DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    return [_row_to_identity(row) for row in rows]


def list_user_identities(user_id: str) -> list[dict[str, Any]]:
    with get_connection() as connection:
        _ensure_auth_schema(connection)
        return _list_user_identities(connection, user_id)


def create_user(*, username: str, password: str, role: str = ROLE_USER) -> dict[str, Any]:
    normalized_username = _normalize_username(username)
    normalized_password = str(password or "")
    normalized_role = ROLE_ADMIN if role == ROLE_ADMIN else ROLE_USER

    if len(normalized_username) < 3:
        raise ValueError("用户名至少需要 3 个字符")
    if len(normalized_password) < 6:
        raise ValueError("密码至少需要 6 个字符")

    now = _utc_now_iso()
    salt = secrets.token_hex(16)
    user_id = str(uuid4())

    try:
        with get_connection() as connection:
            _ensure_auth_schema(connection)
            connection.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, password_salt, role, is_active,
                    primary_auth_method, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    normalized_username,
                    _hash_password(normalized_password, salt),
                    salt,
                    normalized_role,
                    AUTH_METHOD_PASSWORD,
                    USER_STATUS_ACTIVE,
                    now,
                    now,
                ),
            )
            user = _get_user_by_id(connection, user_id)
    except Exception as exc:
        message = str(exc).lower()
        if "uq_users_username_non_empty" in message or "unique" in message:
            raise ValueError("用户名已存在") from exc
        raise

    if user is None:
        raise ValueError("用户创建失败")
    return user


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    normalized_username = _normalize_username(username)
    normalized_password = str(password or "")
    if not normalized_username or not normalized_password:
        return None

    with get_connection() as connection:
        _ensure_auth_schema(connection)
        row = connection.execute(
            """
            SELECT id, username, password_hash, password_salt, role, is_active,
                   primary_auth_method, status, created_at, updated_at
            FROM users
            WHERE username = ?
            LIMIT 1
            """,
            (normalized_username,),
        ).fetchone()

    if row is None or not bool(row["is_active"]):
        return None
    password_hash = str(row["password_hash"] or "")
    password_salt = str(row["password_salt"] or "")
    if not password_hash or not password_salt:
        return None

    expected_hash = _hash_password(normalized_password, password_salt)
    if not hmac.compare_digest(expected_hash, password_hash):
        return None

    return _row_to_user(row)


def count_users() -> int:
    with get_connection() as connection:
        _ensure_auth_schema(connection)
        row = connection.execute("SELECT COUNT(1) AS total FROM users").fetchone()
    return int(row["total"] if row else 0)


def list_users() -> list[dict[str, Any]]:
    with get_connection() as connection:
        _ensure_auth_schema(connection)
        rows = connection.execute(
            """
            SELECT id, username, role, is_active, primary_auth_method, status, created_at, updated_at
            FROM users
            ORDER BY CASE WHEN role = ? THEN 0 ELSE 1 END, created_at ASC, username ASC, id ASC
            """,
            (ROLE_ADMIN,),
        ).fetchall()
    return [_row_to_user(row) for row in rows]


def _count_other_admins(connection: Any, *, excluded_user_id: str) -> int:
    row = connection.execute(
        "SELECT COUNT(1) AS total FROM users WHERE role = ? AND is_active = 1 AND id != ?",
        (ROLE_ADMIN, excluded_user_id),
    ).fetchone()
    return int(row["total"] if row else 0)


def update_user_password(*, user_id: str, password: str) -> dict[str, Any]:
    normalized_user_id = _normalize_text(user_id)
    normalized_password = str(password or "")
    if not normalized_user_id:
        raise ValueError("用户不存在")
    if len(normalized_password) < 6:
        raise ValueError("密码至少需要 6 个字符")

    salt = secrets.token_hex(16)
    now = _utc_now_iso()
    with get_connection() as connection:
        _ensure_auth_schema(connection)
        row = _get_user_by_id(connection, normalized_user_id)
        if row is None:
            raise ValueError("用户不存在")

        connection.execute(
            """
            UPDATE users
            SET password_hash = ?, password_salt = ?, primary_auth_method = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                _hash_password(normalized_password, salt),
                salt,
                AUTH_METHOD_PASSWORD,
                now,
                normalized_user_id,
            ),
        )
        updated_user = _get_user_by_id(connection, normalized_user_id)

    if updated_user is None:
        raise ValueError("用户不存在")
    return updated_user


def update_user_role(*, user_id: str, role: str, actor_user_id: str | None = None) -> dict[str, Any]:
    normalized_user_id = _normalize_text(user_id)
    normalized_role = ROLE_ADMIN if role == ROLE_ADMIN else ROLE_USER
    normalized_actor_user_id = _normalize_text(actor_user_id)
    if not normalized_user_id:
        raise ValueError("用户不存在")

    now = _utc_now_iso()
    with get_connection() as connection:
        _ensure_auth_schema(connection)
        user = _get_user_by_id(connection, normalized_user_id)
        if user is None:
            raise ValueError("用户不存在")

        if user["role"] == ROLE_ADMIN and normalized_role != ROLE_ADMIN:
            if normalized_actor_user_id and normalized_actor_user_id == normalized_user_id:
                raise ValueError("不能移除自己的管理员角色")
            if _count_other_admins(connection, excluded_user_id=normalized_user_id) <= 0:
                raise ValueError("至少需要保留一个启用中的管理员账号")

        connection.execute(
            "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
            (normalized_role, now, normalized_user_id),
        )
        updated_user = _get_user_by_id(connection, normalized_user_id)

    if updated_user is None:
        raise ValueError("用户不存在")
    return updated_user


def update_user_active_status(*, user_id: str, is_active: bool, actor_user_id: str | None = None) -> dict[str, Any]:
    normalized_user_id = _normalize_text(user_id)
    normalized_actor_user_id = _normalize_text(actor_user_id)
    if not normalized_user_id:
        raise ValueError("用户不存在")

    next_is_active = 1 if is_active else 0
    now = _utc_now_iso()
    with get_connection() as connection:
        _ensure_auth_schema(connection)
        user = _get_user_by_id(connection, normalized_user_id)
        if user is None:
            raise ValueError("用户不存在")
        if int(user["is_active"]) == next_is_active:
            return user

        if next_is_active == 0 and user["role"] == ROLE_ADMIN:
            if normalized_actor_user_id and normalized_actor_user_id == normalized_user_id:
                raise ValueError("不能停用当前管理员账号")
            if _count_other_admins(connection, excluded_user_id=normalized_user_id) <= 0:
                raise ValueError("至少需要保留一个启用中的管理员账号")

        connection.execute(
            "UPDATE users SET is_active = ?, updated_at = ? WHERE id = ?",
            (next_is_active, now, normalized_user_id),
        )
        updated_user = _get_user_by_id(connection, normalized_user_id)

    if updated_user is None:
        raise ValueError("用户不存在")
    return updated_user


def _find_identity_for_login(connection: Any, payload: dict[str, str], *, active_only: bool = True) -> dict[str, Any] | None:
    status_filter = "AND status = ?" if active_only else ""

    if payload["unionid"]:
        query = f"""
            SELECT id, user_id, provider, app_id, openid, unionid, nickname_snapshot,
                   avatar_url_snapshot, bound_at, last_login_at, unbound_at, status
            FROM user_identities
            WHERE provider = ? AND unionid = ? {status_filter}
            ORDER BY bound_at DESC, id DESC
            LIMIT 1
        """
        params = [payload["provider"], payload["unionid"]]
        if active_only:
            params.append(IDENTITY_STATUS_ACTIVE)
        row = connection.execute(query, tuple(params)).fetchone()
        if row:
            return _row_to_identity(row)

    if payload["app_id"] and payload["openid"]:
        query = f"""
            SELECT id, user_id, provider, app_id, openid, unionid, nickname_snapshot,
                   avatar_url_snapshot, bound_at, last_login_at, unbound_at, status
            FROM user_identities
            WHERE provider = ? AND app_id = ? AND openid = ? {status_filter}
            ORDER BY bound_at DESC, id DESC
            LIMIT 1
        """
        params = [payload["provider"], payload["app_id"], payload["openid"]]
        if active_only:
            params.append(IDENTITY_STATUS_ACTIVE)
        row = connection.execute(query, tuple(params)).fetchone()
        if row:
            return _row_to_identity(row)

    return None


def _find_user_owned_identity(connection: Any, user_id: str, payload: dict[str, str]) -> dict[str, Any] | None:
    if payload["unionid"]:
        row = connection.execute(
            """
            SELECT id, user_id, provider, app_id, openid, unionid, nickname_snapshot,
                   avatar_url_snapshot, bound_at, last_login_at, unbound_at, status
            FROM user_identities
            WHERE user_id = ? AND provider = ? AND unionid = ?
            ORDER BY bound_at DESC, id DESC
            LIMIT 1
            """,
            (user_id, payload["provider"], payload["unionid"]),
        ).fetchone()
        if row:
            return _row_to_identity(row)

    if payload["app_id"] and payload["openid"]:
        row = connection.execute(
            """
            SELECT id, user_id, provider, app_id, openid, unionid, nickname_snapshot,
                   avatar_url_snapshot, bound_at, last_login_at, unbound_at, status
            FROM user_identities
            WHERE user_id = ? AND provider = ? AND app_id = ? AND openid = ?
            ORDER BY bound_at DESC, id DESC
            LIMIT 1
            """,
            (user_id, payload["provider"], payload["app_id"], payload["openid"]),
        ).fetchone()
        if row:
            return _row_to_identity(row)

    return None


def _create_user(connection: Any, *, primary_auth_method: str, now: str) -> dict[str, Any]:
    user_id = str(uuid4())
    connection.execute(
        """
        INSERT INTO users (id, primary_auth_method, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, primary_auth_method, USER_STATUS_ACTIVE, now, now),
    )
    user = _get_user_by_id(connection, user_id)
    if user is None:
        raise HTTPException(status_code=500, detail="创建用户失败")
    return user


def _touch_user(connection: Any, user_id: str, *, primary_auth_method: str | None = None, now: str) -> None:
    if primary_auth_method:
        connection.execute(
            "UPDATE users SET primary_auth_method = ?, updated_at = ? WHERE id = ?",
            (primary_auth_method, now, user_id),
        )
        return

    connection.execute(
        "UPDATE users SET updated_at = ? WHERE id = ?",
        (now, user_id),
    )


def _create_identity(connection: Any, *, user_id: str, payload: dict[str, str], now: str) -> dict[str, Any]:
    identity_id = str(uuid4())
    connection.execute(
        """
        INSERT INTO user_identities (
            id, user_id, provider, app_id, openid, unionid,
            nickname_snapshot, avatar_url_snapshot, bound_at, last_login_at,
            unbound_at, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            identity_id,
            user_id,
            payload["provider"],
            payload["app_id"],
            payload["openid"],
            payload["unionid"],
            payload["nickname"],
            payload["avatar_url"],
            now,
            now,
            None,
            IDENTITY_STATUS_ACTIVE,
        ),
    )
    identity = _find_user_owned_identity(connection, user_id, payload)
    if identity is None:
        raise HTTPException(status_code=500, detail="创建微信绑定失败")
    return identity


def _update_identity(connection: Any, identity_id: str, payload: dict[str, str], *, status: str, now: str, clear_unbound_at: bool = False) -> dict[str, Any]:
    unbound_at = None if clear_unbound_at else now if status == IDENTITY_STATUS_UNBOUND else None
    connection.execute(
        """
        UPDATE user_identities
        SET app_id = ?,
            openid = ?,
            unionid = ?,
            nickname_snapshot = ?,
            avatar_url_snapshot = ?,
            last_login_at = ?,
            unbound_at = ?,
            status = ?
        WHERE id = ?
        """,
        (
            payload["app_id"],
            payload["openid"],
            payload["unionid"],
            payload["nickname"],
            payload["avatar_url"],
            now,
            unbound_at,
            status,
            identity_id,
        ),
    )
    row = connection.execute(
        """
        SELECT id, user_id, provider, app_id, openid, unionid, nickname_snapshot,
               avatar_url_snapshot, bound_at, last_login_at, unbound_at, status
        FROM user_identities
        WHERE id = ?
        """,
        (identity_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=500, detail="更新微信绑定失败")
    return _row_to_identity(row)


def login_with_wechat(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_identity_payload(payload)
    now = _utc_now_iso()

    with get_connection() as connection:
        _ensure_auth_schema(connection)
        identity = _find_identity_for_login(connection, normalized, active_only=True)
        is_new_user = False
        if identity is None:
            user = _create_user(connection, primary_auth_method=normalized["provider"], now=now)
            identity = _create_identity(connection, user_id=user["id"], payload=normalized, now=now)
            is_new_user = True
        else:
            user = _get_user_by_id(connection, identity["user_id"])
            if user is None:
                raise HTTPException(status_code=404, detail="绑定的用户不存在")
            identity = _update_identity(
                connection,
                identity["id"],
                normalized,
                status=IDENTITY_STATUS_ACTIVE,
                now=now,
            )
            _touch_user(connection, user["id"], now=now)

        user = _get_user_by_id(connection, identity["user_id"])
        if user is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        identities = _list_user_identities(connection, user["id"])
        return {
            "user": user,
            "identity": identity,
            "identities": identities,
            "is_new_user": is_new_user,
        }


def bind_wechat(user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_identity_payload(payload)
    now = _utc_now_iso()

    with get_connection() as connection:
        _ensure_auth_schema(connection)
        user = _get_user_by_id(connection, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="当前用户不存在")

        active_conflict = _find_identity_for_login(connection, normalized, active_only=True)
        if active_conflict and active_conflict["user_id"] != user_id:
            raise HTTPException(status_code=409, detail="该微信身份已绑定到其他账号")

        existing_owned_identity = _find_user_owned_identity(connection, user_id, normalized)
        if existing_owned_identity is not None:
            identity = _update_identity(
                connection,
                existing_owned_identity["id"],
                normalized,
                status=IDENTITY_STATUS_ACTIVE,
                now=now,
                clear_unbound_at=True,
            )
        elif active_conflict is not None:
            identity = _update_identity(
                connection,
                active_conflict["id"],
                normalized,
                status=IDENTITY_STATUS_ACTIVE,
                now=now,
            )
        else:
            identity = _create_identity(connection, user_id=user_id, payload=normalized, now=now)

        next_primary_auth_method = normalized["provider"]
        if str(user.get("primary_auth_method") or "").strip() == AUTH_METHOD_PASSWORD:
            next_primary_auth_method = AUTH_METHOD_PASSWORD
        _touch_user(connection, user_id, primary_auth_method=next_primary_auth_method, now=now)
        user = _get_user_by_id(connection, user_id)
        identities = _list_user_identities(connection, user_id)
        return {
            "user": user,
            "identity": identity,
            "identities": identities,
        }


def unbind_wechat(user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_identity_payload(payload)
    now = _utc_now_iso()

    with get_connection() as connection:
        _ensure_auth_schema(connection)
        user = _get_user_by_id(connection, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="当前用户不存在")

        identity = _find_identity_for_login(connection, normalized, active_only=True)
        if identity is None or identity["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="当前账号未绑定该微信身份")

        active_count_row = connection.execute(
            "SELECT COUNT(1) AS total FROM user_identities WHERE user_id = ? AND status = ?",
            (user_id, IDENTITY_STATUS_ACTIVE),
        ).fetchone()
        active_count = int(active_count_row["total"] if active_count_row else 0)
        if active_count <= 1 and str(user.get("primary_auth_method") or "") == AUTH_PROVIDER_WECHAT:
            raise HTTPException(status_code=409, detail="当前账号仅剩这一种登录方式，无法解绑")

        identity = _update_identity(
            connection,
            identity["id"],
            normalized,
            status=IDENTITY_STATUS_UNBOUND,
            now=now,
        )
        identities = _list_user_identities(connection, user_id)
        return {
            "identity": identity,
            "identities": identities,
        }