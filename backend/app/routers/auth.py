"""认证与第三方身份管理接口。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.security import create_access_token, get_current_user
from app.auth.service import bind_wechat, list_user_identities, login_with_wechat, unbind_wechat

router = APIRouter(prefix="/api/auth", tags=["auth"])


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