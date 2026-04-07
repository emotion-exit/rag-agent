import { getApiBase } from '@/services/runtime';
import type {
  BindWechatResponse,
  IdentitiesResponse,
  UnbindWechatResponse,
  WechatIdentityPayload,
  WechatLoginResponse
} from '@/types/auth';

export const AUTH_ACCESS_TOKEN_STORAGE_KEY = 'rag-agent.auth.access-token.v1';

export function getAccessToken() {
  if (typeof window === 'undefined') {
    return '';
  }

  return window.localStorage.getItem(AUTH_ACCESS_TOKEN_STORAGE_KEY) || '';
}

export function setAccessToken(token: string) {
  if (typeof window === 'undefined') {
    return;
  }

  const normalized = token.trim();
  if (!normalized) {
    window.localStorage.removeItem(AUTH_ACCESS_TOKEN_STORAGE_KEY);
    return;
  }

  window.localStorage.setItem(AUTH_ACCESS_TOKEN_STORAGE_KEY, normalized);
}

export function clearAccessToken() {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.removeItem(AUTH_ACCESS_TOKEN_STORAGE_KEY);
}

export function buildAuthHeaders(): Record<string, string> {
  const token = getAccessToken().trim();
  if (!token) {
    return {};
  }

  return {
    Authorization: `Bearer ${token}`
  };
}

async function requestJson<T>(path: string, init: RequestInit = {}) {
  const response = await fetch(`${getApiBase()}${path}`, {
    ...init,
    headers: {
      ...(init.headers || {}),
      ...buildAuthHeaders()
    }
  });

  if (!response.ok) {
    const fallbackText = `HTTP ${response.status}`;
    let detail = '';
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = String(payload.detail || '').trim();
    } catch {
      detail = detail.trim();
    }
    throw new Error(detail || fallbackText);
  }

  return (await response.json()) as T;
}

export async function loginWithWechat(payload: WechatIdentityPayload) {
  const result = await requestJson<WechatLoginResponse>('/api/auth/login/wechat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
  setAccessToken(result.access_token);
  return result;
}

export function bindWechat(payload: WechatIdentityPayload) {
  return requestJson<BindWechatResponse>('/api/auth/bind-wechat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
}

export function unbindWechat(payload: WechatIdentityPayload) {
  return requestJson<UnbindWechatResponse>('/api/auth/unbind-wechat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
}

export function getIdentities() {
  return requestJson<IdentitiesResponse>('/api/auth/identities');
}