"""JWT 风格 access token 与当前用户依赖。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Header, HTTPException

from app.auth.database import get_connection
from app.auth.service import get_user_by_id
from app.config import settings


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def _json_dumps(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")


def create_access_token(*, user_id: str, auth_method: str) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expires_in = int(settings.jwt_access_token_expire_minutes) * 60
    payload = {
        "sub": user_id,
        "user_id": user_id,
        "auth_method": auth_method,
        "token_type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    header_segment = _b64url_encode(_json_dumps(header))
    payload_segment = _b64url_encode(_json_dumps(payload))
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    token = f"{header_segment}.{payload_segment}.{_b64url_encode(signature)}"
    return token, expires_in


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="无效的访问令牌") from exc

    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    expected_signature = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    actual_signature = _b64url_decode(signature_segment)
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise HTTPException(status_code=401, detail="访问令牌签名校验失败")

    try:
        payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="访问令牌内容非法") from exc

    if payload.get("token_type") != "access":
        raise HTTPException(status_code=401, detail="访问令牌类型不正确")

    expires_at = int(payload.get("exp") or 0)
    if expires_at <= int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status_code=401, detail="访问令牌已过期")

    user_id = str(payload.get("user_id") or payload.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="访问令牌缺少用户标识")

    if is_access_token_revoked(token):
        raise HTTPException(status_code=401, detail="访问令牌已失效")

    return payload


def is_access_token_revoked(token: str) -> bool:
    normalized_token = str(token or "").strip()
    if not normalized_token:
        return False

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM auth_token_revocations WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (now,),
        )
        row = connection.execute(
            "SELECT 1 FROM auth_token_revocations WHERE token = ? LIMIT 1",
            (normalized_token,),
        ).fetchone()
    return row is not None


def revoke_access_token(token: str) -> None:
    normalized_token = str(token or "").strip()
    if not normalized_token:
        return

    expires_at: str | None = None
    try:
        payload = decode_access_token_without_revocation_check(normalized_token)
        exp = int(payload.get("exp") or 0)
        if exp > 0:
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()
    except HTTPException:
        expires_at = None

    with get_connection() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO auth_token_revocations (token, revoked_at, expires_at) VALUES (?, ?, ?)",
            (normalized_token, datetime.now(timezone.utc).isoformat(), expires_at),
        )


def decode_access_token_without_revocation_check(token: str) -> dict[str, Any]:
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="无效的访问令牌") from exc

    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    expected_signature = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    actual_signature = _b64url_decode(signature_segment)
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise HTTPException(status_code=401, detail="访问令牌签名校验失败")

    try:
        payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="访问令牌内容非法") from exc

    if payload.get("token_type") != "access":
        raise HTTPException(status_code=401, detail="访问令牌类型不正确")

    expires_at = int(payload.get("exp") or 0)
    if expires_at <= int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status_code=401, detail="访问令牌已过期")

    user_id = str(payload.get("user_id") or payload.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="访问令牌缺少用户标识")

    return payload


def _extract_bearer_token(authorization: str | None) -> str | None:
    raw_value = str(authorization or "").strip()
    if not raw_value:
        return None
    prefix = "Bearer "
    if not raw_value.startswith(prefix):
        raise HTTPException(status_code=401, detail="Authorization 头必须使用 Bearer 方案")
    token = raw_value[len(prefix):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="访问令牌不能为空")
    return token


def _resolve_user_from_token(token: str) -> dict[str, Any]:
    payload = decode_access_token(token)
    user_id = str(payload.get("user_id") or payload.get("sub") or "").strip()
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="访问令牌对应的用户不存在")
    return user


def get_optional_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any] | None:
    raw_authorization = str(authorization or "").strip()
    if not raw_authorization:
        return None

    try:
        token = _extract_bearer_token(raw_authorization)
        if token is None:
            return None
        return _resolve_user_from_token(token)
    except HTTPException:
        return None


def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    token = _extract_bearer_token(authorization)
    if token is None:
        raise HTTPException(status_code=401, detail="当前请求缺少访问令牌")
    return _resolve_user_from_token(token)