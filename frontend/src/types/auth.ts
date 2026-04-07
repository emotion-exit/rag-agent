export interface AuthUser {
  id: string;
  primary_auth_method: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface UserIdentity {
  id: string;
  user_id: string;
  provider: string;
  app_id: string;
  openid: string;
  unionid: string;
  nickname_snapshot: string;
  avatar_url_snapshot: string;
  bound_at: string;
  last_login_at: string;
  unbound_at: string | null;
  status: string;
}

export interface WechatIdentityPayload {
  app_id?: string;
  openid?: string;
  unionid?: string;
  nickname?: string;
  avatar_url?: string;
}

export interface WechatLoginResponse {
  access_token: string;
  token_type: 'Bearer';
  expires_in: number;
  is_new_user: boolean;
  user: AuthUser;
  identities: UserIdentity[];
}

export interface BindWechatResponse {
  user: AuthUser;
  identity: UserIdentity;
  identities: UserIdentity[];
}

export interface UnbindWechatResponse {
  success: boolean;
  identity: UserIdentity;
  identities: UserIdentity[];
}

export interface IdentitiesResponse {
  user: AuthUser;
  identities: UserIdentity[];
}