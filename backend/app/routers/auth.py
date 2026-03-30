from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.config import (
    USER_EDITABLE_PUBLIC_FRONTEND_CONFIG_FIELDS,
    normalize_public_frontend_config,
    settings,
)
from app.services.auth import (
    ROLE_ADMIN,
    ROLE_USER,
    authenticate_user,
    count_users,
    create_auth_token,
    create_user,
    get_current_user,
    get_request_user,
    is_admin,
    list_users,
    revoke_auth_token,
    update_user_active_status,
    update_user_password,
    update_user_role,
)
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


def _require_admin_user(request: Request) -> dict:
    user = get_request_user(request) or get_current_user(required=True)
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可执行该操作")
    return user


@router.post("/login")
async def login(payload: LoginRequest):
    user = authenticate_user(payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token_payload = create_auth_token(user["user_id"])
    return {
        "success": True,
        "token": token_payload["token"],
        "expires_at": token_payload["expires_at"],
        "user": user,
        "features": {
            "private_knowledge_base_enabled": bool(settings.private_knowledge_base_enabled),
            "open_registration_enabled": bool(settings.open_registration_enabled),
        },
    }


@router.post("/register")
async def register(payload: RegisterRequest):
    if not settings.open_registration_enabled:
        raise HTTPException(status_code=403, detail="当前未开放注册")

    try:
        user = create_user(
            username=payload.username,
            password=payload.password,
            role=ROLE_USER,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    token_payload = create_auth_token(user["user_id"])
    return {
        "success": True,
        "token": token_payload["token"],
        "expires_at": token_payload["expires_at"],
        "user": user,
        "features": {
            "private_knowledge_base_enabled": bool(settings.private_knowledge_base_enabled),
            "open_registration_enabled": bool(settings.open_registration_enabled),
        },
    }


@router.post("/logout")
async def logout(request: Request):
    token = str(request.headers.get("authorization", "") or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        token = str(request.headers.get("x-auth-token", "") or "").strip()
    if token:
        revoke_auth_token(token)
    return {"success": True}


@router.get("/me")
async def me(request: Request):
    user = get_request_user(request) or get_current_user(required=True)
    return {
        "user": user,
        "features": {
            "private_knowledge_base_enabled": bool(settings.private_knowledge_base_enabled),
            "open_registration_enabled": bool(settings.open_registration_enabled),
        },
    }


@router.get("/public-config")
async def get_current_user_runtime_config(request: Request):
    user = get_request_user(request) or get_current_user(required=True)
    allowed_fields = None if is_admin(user) else USER_EDITABLE_PUBLIC_FRONTEND_CONFIG_FIELDS
    return {
        "config": get_user_public_config(
            str(user.get("user_id") or ""),
            allowed_fields=allowed_fields,
        ),
        "has_overrides": bool(
            get_user_public_config_overrides(
                str(user.get("user_id") or ""),
                allowed_fields=allowed_fields,
            )
        ),
    }


@router.put("/public-config")
async def save_current_user_runtime_config(payload: dict, request: Request):
    user = get_request_user(request) or get_current_user(required=True)
    allowed_fields = None if is_admin(user) else USER_EDITABLE_PUBLIC_FRONTEND_CONFIG_FIELDS
    saved_config = save_user_public_config(
        str(user.get("user_id") or ""),
        payload,
        allowed_fields=allowed_fields,
    )
    return {"success": True, "config": saved_config}


@router.delete("/public-config")
async def reset_current_user_runtime_config(request: Request):
    user = get_request_user(request) or get_current_user(required=True)
    config = reset_user_public_config(str(user.get("user_id") or ""))
    return {"success": True, "config": config}


@router.get("/public-config/system")
async def get_system_runtime_config(request: Request):
    _require_admin_user(request)
    return {"config": get_system_public_config()}


@router.put("/public-config/system")
async def save_system_runtime_config(payload: dict, request: Request):
    _require_admin_user(request)
    saved_config = save_system_public_config(normalize_public_frontend_config(payload))
    return {"success": True, "config": saved_config}


@router.delete("/public-config/system")
async def reset_system_runtime_config(request: Request):
    _require_admin_user(request)
    config = reset_system_public_config()
    return {"success": True, "config": config}


@router.get("/bootstrap")
async def bootstrap():
    return {
        "features": {
            "private_knowledge_base_enabled": bool(settings.private_knowledge_base_enabled),
            "open_registration_enabled": bool(settings.open_registration_enabled),
        },
        "has_users": count_users() > 0,
    }


@router.get("/users")
async def admin_list_users(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
):
    _require_admin_user(request)
    return list_users(page=page, page_size=page_size)


@router.post("/users")
async def admin_create_user(request: Request, payload: AdminCreateUserRequest):
    _require_admin_user(request)
    normalized_role = ROLE_ADMIN if payload.role == ROLE_ADMIN else ROLE_USER
    try:
        user = create_user(
            username=payload.username,
            password=payload.password,
            role=normalized_role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "user": user}


@router.patch("/users/{user_id}")
async def admin_update_user(user_id: str, payload: AdminUpdateUserRequest, request: Request):
    actor = _require_admin_user(request)

    if payload.role is None and payload.is_active is None:
        raise HTTPException(status_code=400, detail="至少提供一个更新字段")

    try:
        user = None
        if payload.role is not None:
            user = update_user_role(
                user_id=user_id,
                role=payload.role,
                actor_user_id=str(actor.get("user_id") or ""),
            )
        if payload.is_active is not None:
            user = update_user_active_status(
                user_id=user_id,
                is_active=payload.is_active,
                actor_user_id=str(actor.get("user_id") or ""),
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"success": True, "user": user}


@router.post("/users/{user_id}/reset-password")
async def admin_reset_user_password(user_id: str, payload: AdminResetPasswordRequest, request: Request):
    _require_admin_user(request)
    try:
        user = update_user_password(user_id=user_id, password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "user": user}