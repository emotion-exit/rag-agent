import { reactive, readonly } from 'vue';
import { getApiBase } from '@/services/runtime';

export const AUTH_SESSION_STORAGE_KEY = 'rag-agent.auth-session.v1';

export interface AuthUser {
  user_id: string;
  username: string;
  role: 'admin' | 'user';
}

export interface ManagedAuthUser extends AuthUser {
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ManagedUserListResult {
  items: ManagedAuthUser[];
  total: number;
  active_total: number;
  admin_total: number;
  page: number;
  page_size: number;
}

export interface AuthFeatures {
  private_knowledge_base_enabled: boolean;
  open_registration_enabled: boolean;
}

export interface AuthSession {
  token: string;
  expires_at: string;
  user: AuthUser;
  features: AuthFeatures;
}

interface AuthMeResponse {
  user: AuthUser;
  features: AuthFeatures;
}

interface AdminUserListResponse {
  items: ManagedAuthUser[];
  total?: number;
  active_total?: number;
  admin_total?: number;
  page?: number;
  page_size?: number;
}

interface AdminUserMutationResponse {
  success: boolean;
  user: ManagedAuthUser;
}

function loadStoredSession(): AuthSession | null {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    const rawValue = window.localStorage.getItem(AUTH_SESSION_STORAGE_KEY);
    if (!rawValue) {
      return null;
    }
    return JSON.parse(rawValue) as AuthSession;
  } catch {
    return null;
  }
}

const authState = reactive({
  session: loadStoredSession() as AuthSession | null,
  ready: false
});

export function useAuthState() {
  return readonly(authState);
}

export function getAuthSession(): AuthSession | null {
  return authState.session;
}

export function getAuthToken(): string {
  return String(authState.session?.token || '').trim();
}

export function hasAuthSession(): boolean {
  return !!getAuthToken();
}

export function isAdminUser(): boolean {
  return authState.session?.user.role === 'admin';
}

export function saveAuthSession(session: AuthSession): void {
  authState.session = session;
  authState.ready = true;
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(
      AUTH_SESSION_STORAGE_KEY,
      JSON.stringify(session)
    );
  }
}

export function clearAuthSession(): void {
  authState.session = null;
  authState.ready = true;
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(AUTH_SESSION_STORAGE_KEY);
  }
}

export function buildAuthHeaders(): Record<string, string> {
  const token = getAuthToken();
  if (!token) {
    return {};
  }
  return {
    Authorization: `Bearer ${token}`
  };
}

export async function refreshAuthSession(): Promise<AuthSession | null> {
  const currentSession = getAuthSession();
  if (!currentSession?.token) {
    authState.ready = true;
    return null;
  }

  const response = await fetch(`${getApiBase()}/api/auth/me`, {
    headers: buildAuthHeaders()
  });

  if (!response.ok) {
    clearAuthSession();
    return null;
  }

  const payload = (await response.json()) as AuthMeResponse;
  const nextSession: AuthSession = {
    ...currentSession,
    user: payload.user,
    features: payload.features
  };
  saveAuthSession(nextSession);
  return nextSession;
}

export function markAuthReady(): void {
  authState.ready = true;
}

async function parseApiError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return String(payload.detail || '').trim() || `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

export async function fetchManagedUsers(options?: {
  page?: number;
  pageSize?: number;
}): Promise<ManagedUserListResult> {
  const page = Math.max(1, Number(options?.page || 1));
  const pageSize = Math.max(1, Number(options?.pageSize || 10));
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize)
  });

  const response = await fetch(
    `${getApiBase()}/api/auth/users?${query.toString()}`,
    {
      headers: buildAuthHeaders()
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const payload = (await response.json()) as AdminUserListResponse;
  const items = Array.isArray(payload.items) ? payload.items : [];

  return {
    items,
    total: Math.max(0, Number(payload.total || 0)),
    active_total: Math.max(0, Number(payload.active_total || 0)),
    admin_total: Math.max(0, Number(payload.admin_total || 0)),
    page: Math.max(1, Number(payload.page || page)),
    page_size: Math.max(1, Number(payload.page_size || pageSize))
  };
}

export async function createManagedUser(payload: {
  username: string;
  password: string;
  role: 'admin' | 'user';
}): Promise<ManagedAuthUser> {
  const response = await fetch(`${getApiBase()}/api/auth/users`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...buildAuthHeaders()
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const result = (await response.json()) as AdminUserMutationResponse;
  return result.user;
}

export async function updateManagedUser(
  userId: string,
  payload: {
    role?: 'admin' | 'user';
    is_active?: boolean;
  }
): Promise<ManagedAuthUser> {
  const response = await fetch(`${getApiBase()}/api/auth/users/${userId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...buildAuthHeaders()
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const result = (await response.json()) as AdminUserMutationResponse;
  return result.user;
}

export async function resetManagedUserPassword(
  userId: string,
  password: string
): Promise<ManagedAuthUser> {
  const response = await fetch(
    `${getApiBase()}/api/auth/users/${userId}/reset-password`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...buildAuthHeaders()
      },
      body: JSON.stringify({ password })
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const result = (await response.json()) as AdminUserMutationResponse;
  return result.user;
}
