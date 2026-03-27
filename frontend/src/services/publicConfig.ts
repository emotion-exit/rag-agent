import { buildAuthHeaders } from '@/services/auth';
import { getApiBase } from '@/services/runtime';

export const PUBLIC_FRONTEND_CONFIG_STORAGE_KEY = 'rag-agent.public-config.v1';

let currentPublicFrontendConfig: PublicFrontendConfig | null = null;

export interface PublicFrontendConfig {
  EMBEDDING_PROVIDER: string;
  EMBEDDING_MAX_INPUT_TOKENS: number;
  EMBEDDING_TARGET_CHUNK_TOKENS: number;
  EMBEDDING_CHUNK_OVERLAP_TOKENS: number;
  EMBEDDING_TOKENIZER_MODEL: string;
  EMBEDDING_TOKENIZER_ENCODING: string;
  RERANKER_REQUEST_TIMEOUT: number;
  RETRIEVAL_CANDIDATE_LIMIT: number;
  RETRIEVAL_FINAL_CONTEXT_LIMIT: number;
  RETRIEVAL_SOURCE_LIMIT: number;
  RETRIEVAL_QUERY_EXPANSION_COUNT: number;
  REFLECTION_TOKENS: number;
  CHAT_TEMPERATURE: number;
  OPENROUTER_SITE_URL: string;
  OPENROUTER_APP_TITLE: string;
  OPENROUTER_CATEGORIES: string;
}

export const PUBLIC_FRONTEND_CONFIG_KEYS = [
  'EMBEDDING_PROVIDER',
  'EMBEDDING_MAX_INPUT_TOKENS',
  'EMBEDDING_TARGET_CHUNK_TOKENS',
  'EMBEDDING_CHUNK_OVERLAP_TOKENS',
  'EMBEDDING_TOKENIZER_MODEL',
  'EMBEDDING_TOKENIZER_ENCODING',
  'RERANKER_REQUEST_TIMEOUT',
  'RETRIEVAL_CANDIDATE_LIMIT',
  'RETRIEVAL_FINAL_CONTEXT_LIMIT',
  'RETRIEVAL_SOURCE_LIMIT',
  'RETRIEVAL_QUERY_EXPANSION_COUNT',
  'REFLECTION_TOKENS',
  'CHAT_TEMPERATURE',
  'OPENROUTER_SITE_URL',
  'OPENROUTER_APP_TITLE',
  'OPENROUTER_CATEGORIES'
] as const;

export type PublicFrontendConfigKey =
  (typeof PUBLIC_FRONTEND_CONFIG_KEYS)[number];

const numericPublicKeys = new Set<PublicFrontendConfigKey>([
  'EMBEDDING_MAX_INPUT_TOKENS',
  'EMBEDDING_TARGET_CHUNK_TOKENS',
  'EMBEDDING_CHUNK_OVERLAP_TOKENS',
  'RERANKER_REQUEST_TIMEOUT',
  'RETRIEVAL_CANDIDATE_LIMIT',
  'RETRIEVAL_FINAL_CONTEXT_LIMIT',
  'RETRIEVAL_SOURCE_LIMIT',
  'RETRIEVAL_QUERY_EXPANSION_COUNT',
  'REFLECTION_TOKENS',
  'CHAT_TEMPERATURE'
]);

export function createEmptyPublicFrontendConfig(): PublicFrontendConfig {
  return {
    EMBEDDING_PROVIDER: '',
    EMBEDDING_MAX_INPUT_TOKENS: 0,
    EMBEDDING_TARGET_CHUNK_TOKENS: 0,
    EMBEDDING_CHUNK_OVERLAP_TOKENS: 0,
    EMBEDDING_TOKENIZER_MODEL: '',
    EMBEDDING_TOKENIZER_ENCODING: '',
    RERANKER_REQUEST_TIMEOUT: 0,
    RETRIEVAL_CANDIDATE_LIMIT: 0,
    RETRIEVAL_FINAL_CONTEXT_LIMIT: 0,
    RETRIEVAL_SOURCE_LIMIT: 0,
    RETRIEVAL_QUERY_EXPANSION_COUNT: 0,
    REFLECTION_TOKENS: 0,
    CHAT_TEMPERATURE: 0,
    OPENROUTER_SITE_URL: '',
    OPENROUTER_APP_TITLE: '',
    OPENROUTER_CATEGORIES: ''
  };
}

export function normalizePublicFrontendConfig(
  source: Partial<PublicFrontendConfig>,
  fallback: Partial<PublicFrontendConfig> = currentPublicFrontendConfig ||
    createEmptyPublicFrontendConfig()
): PublicFrontendConfig {
  const normalized = {} as Record<PublicFrontendConfigKey, string | number>;

  for (const key of PUBLIC_FRONTEND_CONFIG_KEYS) {
    const fallbackValue = fallback[key];
    const rawValue = source[key];

    if (numericPublicKeys.has(key)) {
      const nextValue = Number(rawValue);
      normalized[key] = Number.isFinite(nextValue)
        ? nextValue
        : Number(fallbackValue ?? 0);
      continue;
    }

    normalized[key] = String(rawValue ?? fallbackValue ?? '');
  }

  return normalized as PublicFrontendConfig;
}

function clearLegacyPublicConfigStorage(): void {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.removeItem(PUBLIC_FRONTEND_CONFIG_STORAGE_KEY);
}

function setCurrentPublicFrontendConfig(
  source: Partial<PublicFrontendConfig>
): PublicFrontendConfig {
  currentPublicFrontendConfig = normalizePublicFrontendConfig(source);
  return { ...currentPublicFrontendConfig };
}

async function parseApiError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return String(payload.detail || '').trim() || `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

export async function loadPublicFrontendConfig(): Promise<PublicFrontendConfig> {
  clearLegacyPublicConfigStorage();

  const response = await fetch(`${getApiBase()}/api/auth/public-config`, {
    headers: buildAuthHeaders()
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const payload = (await response.json()) as {
    config?: Partial<PublicFrontendConfig>;
  };
  return setCurrentPublicFrontendConfig(payload.config || {});
}

export async function loadSystemPublicFrontendConfig(): Promise<PublicFrontendConfig> {
  clearLegacyPublicConfigStorage();

  const response = await fetch(
    `${getApiBase()}/api/auth/public-config/system`,
    {
      headers: buildAuthHeaders()
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const payload = (await response.json()) as {
    config?: Partial<PublicFrontendConfig>;
  };
  return setCurrentPublicFrontendConfig(payload.config || {});
}

export async function savePublicFrontendConfig(
  source: Partial<PublicFrontendConfig>
): Promise<PublicFrontendConfig> {
  clearLegacyPublicConfigStorage();
  const normalized = normalizePublicFrontendConfig(source);
  const response = await fetch(`${getApiBase()}/api/auth/public-config`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...buildAuthHeaders()
    },
    body: JSON.stringify(normalized)
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const payload = (await response.json()) as {
    config?: Partial<PublicFrontendConfig>;
  };
  return setCurrentPublicFrontendConfig(payload.config || normalized);
}

export async function resetPublicFrontendConfig(): Promise<PublicFrontendConfig> {
  clearLegacyPublicConfigStorage();
  const response = await fetch(`${getApiBase()}/api/auth/public-config`, {
    method: 'DELETE',
    headers: buildAuthHeaders()
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const payload = (await response.json()) as {
    config?: Partial<PublicFrontendConfig>;
  };
  return setCurrentPublicFrontendConfig(payload.config || {});
}

export async function saveSystemPublicFrontendConfig(
  source: Partial<PublicFrontendConfig>
): Promise<PublicFrontendConfig> {
  clearLegacyPublicConfigStorage();
  const normalized = normalizePublicFrontendConfig(source);
  const response = await fetch(
    `${getApiBase()}/api/auth/public-config/system`,
    {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...buildAuthHeaders()
      },
      body: JSON.stringify(normalized)
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const payload = (await response.json()) as {
    config?: Partial<PublicFrontendConfig>;
  };
  return setCurrentPublicFrontendConfig(payload.config || normalized);
}

export async function resetSystemPublicFrontendConfig(): Promise<PublicFrontendConfig> {
  clearLegacyPublicConfigStorage();
  const response = await fetch(
    `${getApiBase()}/api/auth/public-config/system`,
    {
      method: 'DELETE',
      headers: buildAuthHeaders()
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const payload = (await response.json()) as {
    config?: Partial<PublicFrontendConfig>;
  };
  return setCurrentPublicFrontendConfig(payload.config || {});
}

export function buildPublicConfigHeaders(
  source?: Partial<PublicFrontendConfig>
): Record<string, string> {
  if (!source) {
    return {
      ...buildAuthHeaders()
    };
  }

  const normalized = normalizePublicFrontendConfig(source);

  return {
    ...buildAuthHeaders(),
    'X-Rag-Public-Config': JSON.stringify(normalized)
  };
}
