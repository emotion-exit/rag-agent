import {
  DEFAULT_DESKTOP_CONFIG,
  type DesktopAppConfig
} from '@/services/runtime';

export const PUBLIC_FRONTEND_CONFIG_STORAGE_KEY = 'rag-agent.public-config.v1';

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
  'CHAT_TEMPERATURE',
  'OPENROUTER_SITE_URL',
  'OPENROUTER_APP_TITLE',
  'OPENROUTER_CATEGORIES',
  'CHROMA_PERSIST_DIR',
  'UPLOAD_DIR',
  'CORS_ORIGINS'
] as const;

export type PublicFrontendConfigKey =
  (typeof PUBLIC_FRONTEND_CONFIG_KEYS)[number];

export type PublicFrontendConfig = Pick<
  DesktopAppConfig,
  PublicFrontendConfigKey
>;

const numericPublicKeys = new Set<PublicFrontendConfigKey>([
  'EMBEDDING_MAX_INPUT_TOKENS',
  'EMBEDDING_TARGET_CHUNK_TOKENS',
  'EMBEDDING_CHUNK_OVERLAP_TOKENS',
  'RERANKER_REQUEST_TIMEOUT',
  'RETRIEVAL_CANDIDATE_LIMIT',
  'RETRIEVAL_FINAL_CONTEXT_LIMIT',
  'RETRIEVAL_SOURCE_LIMIT',
  'RETRIEVAL_QUERY_EXPANSION_COUNT',
  'CHAT_TEMPERATURE'
]);

export const DEFAULT_PUBLIC_FRONTEND_CONFIG: PublicFrontendConfig =
  extractPublicFrontendConfig(DEFAULT_DESKTOP_CONFIG);

export function extractPublicFrontendConfig(
  source: Partial<DesktopAppConfig>
): PublicFrontendConfig {
  const normalized = {} as Record<PublicFrontendConfigKey, string | number>;

  for (const key of PUBLIC_FRONTEND_CONFIG_KEYS) {
    const fallback = DEFAULT_DESKTOP_CONFIG[key];
    const rawValue = source[key];

    if (numericPublicKeys.has(key)) {
      const nextValue = Number(rawValue);
      normalized[key] = Number.isFinite(nextValue)
        ? nextValue
        : Number(fallback);
      continue;
    }

    normalized[key] = String(rawValue ?? fallback);
  }

  return normalized as PublicFrontendConfig;
}

export function cloneDefaultPublicFrontendConfig(): PublicFrontendConfig {
  return { ...DEFAULT_PUBLIC_FRONTEND_CONFIG };
}

export function loadPublicFrontendConfig(): PublicFrontendConfig {
  if (typeof window === 'undefined') {
    return cloneDefaultPublicFrontendConfig();
  }

  try {
    const rawValue = window.localStorage.getItem(
      PUBLIC_FRONTEND_CONFIG_STORAGE_KEY
    );
    if (!rawValue) {
      return cloneDefaultPublicFrontendConfig();
    }

    const parsed = JSON.parse(rawValue) as Partial<DesktopAppConfig>;
    return extractPublicFrontendConfig(parsed);
  } catch {
    return cloneDefaultPublicFrontendConfig();
  }
}

export function savePublicFrontendConfig(
  source: Partial<DesktopAppConfig>
): PublicFrontendConfig {
  const normalized = extractPublicFrontendConfig(source);

  if (typeof window !== 'undefined') {
    window.localStorage.setItem(
      PUBLIC_FRONTEND_CONFIG_STORAGE_KEY,
      JSON.stringify(normalized)
    );
  }

  return normalized;
}

export function resetPublicFrontendConfig(): PublicFrontendConfig {
  const defaults = cloneDefaultPublicFrontendConfig();

  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(PUBLIC_FRONTEND_CONFIG_STORAGE_KEY);
  }

  return defaults;
}

export function buildPublicConfigHeaders(
  source?: Partial<DesktopAppConfig>
): Record<string, string> {
  const normalized = source
    ? extractPublicFrontendConfig(source)
    : loadPublicFrontendConfig();

  return {
    'X-Rag-Public-Config': JSON.stringify(normalized)
  };
}
