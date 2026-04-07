"""微信身份登录与绑定服务。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.auth.database import get_connection


AUTH_PROVIDER_WECHAT = "wechat"
IDENTITY_STATUS_ACTIVE = "active"
IDENTITY_STATUS_UNBOUND = "unbound"
USER_STATUS_ACTIVE = "active"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: str | None) -> str:
    return str(value or "").strip()


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
        "SELECT id, primary_auth_method, status, created_at, updated_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
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
        return _list_user_identities(connection, user_id)


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

        _touch_user(connection, user_id, primary_auth_method=normalized["provider"], now=now)
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
        identity = _find_identity_for_login(connection, normalized, active_only=True)
        if identity is None or identity["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="当前账号未绑定该微信身份")

        active_count_row = connection.execute(
            "SELECT COUNT(1) AS total FROM user_identities WHERE user_id = ? AND status = ?",
            (user_id, IDENTITY_STATUS_ACTIVE),
        ).fetchone()
        active_count = int(active_count_row["total"] if active_count_row else 0)
        if active_count <= 1:
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