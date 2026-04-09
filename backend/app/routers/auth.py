"""认证与第三方身份管理接口。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.auth.security import create_access_token, get_current_user, revoke_access_token
from app.auth.service import (
    ROLE_ADMIN,
    ROLE_USER,
    authenticate_user,
    bind_wechat,
    count_users,
    create_user,
    list_user_identities,
    list_users,
    login_with_wechat,
    unbind_wechat,
    update_user_active_status,
    update_user_password,
    update_user_role,
)
from app.config import settings
from app.services.public_config import (
    get_system_public_config,
    get_user_public_config,
    get_user_public_config_overrides,
    reset_system_public_config,
    reset_user_public_config,
    save_system_public_config,
    save_user_public_config,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _build_features_payload() -> dict[str, bool]:
    return {
        "private_knowledge_base_enabled": bool(settings.private_knowledge_base_enabled),
        "open_registration_enabled": bool(settings.open_registration_enabled),
    }


def _serialize_legacy_user(user: dict) -> dict:
    return {
        "user_id": str(user.get("id") or user.get("user_id") or ""),
        "username": str(user.get("username") or ""),
        "role": str(user.get("role") or ROLE_USER),
        "is_active": bool(user.get("is_active", True)),
        "primary_auth_method": str(user.get("primary_auth_method") or ""),
        "created_at": str(user.get("created_at") or ""),
        "updated_at": str(user.get("updated_at") or ""),
    }


def _extract_request_token(authorization: str | None, x_auth_token: str | None = None) -> str:
    raw_authorization = str(authorization or "").strip()
    if raw_authorization.lower().startswith("bearer "):
        return raw_authorization[7:].strip()

    header_token = str(x_auth_token or "").strip()
    if header_token:
        return header_token

    return ""


def _require_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    role = str(current_user.get("role") or ROLE_USER)
    if role != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="仅管理员可执行该操作")
    return current_user


class LoginRequest(BaseModel):
    username: str = Field(default="")
    password: str = Field(default="")


class RegisterRequest(BaseModel):
    username: str = Field(default="")
    password: str = Field(default="")


class AdminCreateUserRequest(BaseModel):
    username: str = Field(default="")
    password: str = Field(default="")
    role: str = Field(default=ROLE_USER)


class AdminUpdateUserRequest(BaseModel):
    role: str | None = Field(default=None)
    is_active: bool | None = Field(default=None)


class AdminResetPasswordRequest(BaseModel):
    password: str = Field(default="")


class WechatIdentityPayload(BaseModel):
    app_id: str = ""
    openid: str = ""
    unionid: str = ""
    nickname: str = ""
    avatar_url: str = ""


class AuthUserResponse(BaseModel):
    id: str
    primary_auth_method: str
    status: str
    created_at: str
    updated_at: str


class UserIdentityResponse(BaseModel):
    id: str
    user_id: str
    provider: str
    app_id: str
    openid: str
    unionid: str
    nickname_snapshot: str
    avatar_url_snapshot: str
    bound_at: str
    last_login_at: str
    unbound_at: str | None = None
    status: str


class WechatLoginResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    is_new_user: bool
    user: AuthUserResponse
    identities: list[UserIdentityResponse]


class BindWechatResponse(BaseModel):
    user: AuthUserResponse
    identity: UserIdentityResponse
    identities: list[UserIdentityResponse]


class UnbindWechatResponse(BaseModel):
    success: bool = True
    identity: UserIdentityResponse
    identities: list[UserIdentityResponse]


class IdentitiesResponse(BaseModel):
    user: AuthUserResponse
    identities: list[UserIdentityResponse]


@router.post("/login")
async def login(payload: LoginRequest):
    user = authenticate_user(payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token, expires_in = create_access_token(
        user_id=str(user.get("id") or ""),
        auth_method=str(user.get("primary_auth_method") or "password"),
    )
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
    return {
        "success": True,
        "token": token,
        "expires_at": expires_at,
        "user": _serialize_legacy_user(user),
        "features": _build_features_payload(),
    }


@router.post("/register")
async def register(payload: RegisterRequest):
    if not settings.open_registration_enabled:
        raise HTTPException(status_code=403, detail="当前未开放注册")

    try:
        user = create_user(username=payload.username, password=payload.password, role=ROLE_USER)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token, expires_in = create_access_token(
        user_id=str(user.get("id") or ""),
        auth_method=str(user.get("primary_auth_method") or "password"),
    )
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
    return {
        "success": True,
        "token": token,
        "expires_at": expires_at,
        "user": _serialize_legacy_user(user),
        "features": _build_features_payload(),
    }


@router.post("/logout")
async def logout(
    authorization: str | None = Header(default=None),
    x_auth_token: str | None = Header(default=None),
):
    token = _extract_request_token(authorization, x_auth_token)
    if token:
        revoke_access_token(token)
    return {"success": True}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return {
        "user": _serialize_legacy_user(current_user),
        "features": _build_features_payload(),
    }


@router.get("/public-config")
async def get_current_user_runtime_config(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user.get("id") or current_user.get("user_id") or "")
    return {
        "config": get_user_public_config(user_id),
        "has_overrides": bool(get_user_public_config_overrides(user_id)),
    }


@router.put("/public-config")
async def save_current_user_runtime_config(payload: dict, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user.get("id") or current_user.get("user_id") or "")
    config = save_user_public_config(user_id, payload)
    return {"success": True, "config": config}


@router.delete("/public-config")
async def reset_current_user_runtime_config(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user.get("id") or current_user.get("user_id") or "")
    config = reset_user_public_config(user_id)
    return {"success": True, "config": config}


@router.get("/public-config/system")
async def get_system_runtime_config(current_user: dict = Depends(_require_admin_user)):
    del current_user
    return {"config": get_system_public_config()}


@router.put("/public-config/system")
async def save_system_runtime_config(payload: dict, current_user: dict = Depends(_require_admin_user)):
    del current_user
    config = save_system_public_config(payload)
    return {"success": True, "config": config}


@router.delete("/public-config/system")
async def reset_system_runtime_config(current_user: dict = Depends(_require_admin_user)):
    del current_user
    config = reset_system_public_config()
    return {"success": True, "config": config}


@router.get("/bootstrap")
async def bootstrap():
    return {
        "features": _build_features_payload(),
        "has_users": count_users() > 0,
    }


@router.post("/login/wechat", response_model=WechatLoginResponse)
async def login_wechat(request: WechatIdentityPayload):
    result = login_with_wechat(request.model_dump())
    token, expires_in = create_access_token(
        user_id=result["user"]["id"],
        auth_method="wechat",
    )
    return WechatLoginResponse(
        access_token=token,
        expires_in=expires_in,
        is_new_user=bool(result["is_new_user"]),
        user=AuthUserResponse.model_validate(result["user"]),
        identities=[
            UserIdentityResponse.model_validate(identity)
            for identity in result["identities"]
        ],
    )


@router.post("/bind-wechat", response_model=BindWechatResponse)
async def bind_wechat_identity(
    request: WechatIdentityPayload,
    current_user: dict = Depends(get_current_user),
):
    result = bind_wechat(current_user["id"], request.model_dump())
    return BindWechatResponse(
        user=AuthUserResponse.model_validate(result["user"]),
        identity=UserIdentityResponse.model_validate(result["identity"]),
        identities=[
            UserIdentityResponse.model_validate(identity)
            for identity in result["identities"]
        ],
    )


@router.post("/unbind-wechat", response_model=UnbindWechatResponse)
async def unbind_wechat_identity(
    request: WechatIdentityPayload,
    current_user: dict = Depends(get_current_user),
):
    result = unbind_wechat(current_user["id"], request.model_dump())
    return UnbindWechatResponse(
        identity=UserIdentityResponse.model_validate(result["identity"]),
        identities=[
            UserIdentityResponse.model_validate(identity)
            for identity in result["identities"]
        ],
    )


@router.get("/identities", response_model=IdentitiesResponse)
async def get_identities(current_user: dict = Depends(get_current_user)):
    identities = list_user_identities(current_user["id"])
    return IdentitiesResponse(
        user=AuthUserResponse.model_validate(current_user),
        identities=[
            UserIdentityResponse.model_validate(identity)
            for identity in identities
        ],
    )


@router.get("/users")
async def admin_list_users(current_user: dict = Depends(_require_admin_user)):
    return {"items": [_serialize_legacy_user(user) for user in list_users()]}


@router.post("/users")
async def admin_create_user(payload: AdminCreateUserRequest, current_user: dict = Depends(_require_admin_user)):
    del current_user
    try:
        user = create_user(
            username=payload.username,
            password=payload.password,
            role=ROLE_ADMIN if payload.role == ROLE_ADMIN else ROLE_USER,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "user": _serialize_legacy_user(user)}


@router.patch("/users/{user_id}")
async def admin_update_user(
    user_id: str,
    payload: AdminUpdateUserRequest,
    current_user: dict = Depends(_require_admin_user),
):
    if payload.role is None and payload.is_active is None:
        raise HTTPException(status_code=400, detail="至少提供一个更新字段")

    try:
        user = None
        if payload.role is not None:
            user = update_user_role(
                user_id=user_id,
                role=payload.role,
                actor_user_id=str(current_user.get("id") or ""),
            )
        if payload.is_active is not None:
            user = update_user_active_status(
                user_id=user_id,
                is_active=payload.is_active,
                actor_user_id=str(current_user.get("id") or ""),
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"success": True, "user": _serialize_legacy_user(user or {})}


@router.post("/users/{user_id}/reset-password")
async def admin_reset_user_password(
    user_id: str,
    payload: AdminResetPasswordRequest,
    current_user: dict = Depends(_require_admin_user),
):
    del current_user
    try:
        user = update_user_password(user_id=user_id, password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "user": _serialize_legacy_user(user)}