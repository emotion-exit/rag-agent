import { buildAuthHeaders } from '@/services/auth';

export const PUBLIC_FRONTEND_CONFIG_STORAGE_KEY = 'rag-agent.public-config.v1';

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
  CHROMA_PERSIST_DIR: string;
  UPLOAD_DIR: string;
  CORS_ORIGINS: string;
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
  'OPENROUTER_CATEGORIES',
  'CHROMA_PERSIST_DIR',
  'UPLOAD_DIR',
  'CORS_ORIGINS'
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

export const DEFAULT_PUBLIC_FRONTEND_CONFIG: PublicFrontendConfig = {
  EMBEDDING_PROVIDER: 'openai',
  EMBEDDING_MAX_INPUT_TOKENS: 512,
  EMBEDDING_TARGET_CHUNK_TOKENS: 384,
  EMBEDDING_CHUNK_OVERLAP_TOKENS: 48,
  EMBEDDING_TOKENIZER_MODEL: '',
  EMBEDDING_TOKENIZER_ENCODING: 'cl100k_base',
  RERANKER_REQUEST_TIMEOUT: 20,
  RETRIEVAL_CANDIDATE_LIMIT: 12,
  RETRIEVAL_FINAL_CONTEXT_LIMIT: 3,
  RETRIEVAL_SOURCE_LIMIT: 3,
  RETRIEVAL_QUERY_EXPANSION_COUNT: 2,
  REFLECTION_TOKENS: 256,
  CHAT_TEMPERATURE: 0,
  OPENROUTER_SITE_URL: 'https://localhost.invalid',
  OPENROUTER_APP_TITLE: 'RAG.Agent Web',
  OPENROUTER_CATEGORIES: 'general-chat',
  CHROMA_PERSIST_DIR: './data/chroma',
  UPLOAD_DIR: './data/uploads',
  CORS_ORIGINS: 'http://localhost:5173,http://localhost:3000,null'
};

export function extractPublicFrontendConfig(
  source: Partial<PublicFrontendConfig>
): PublicFrontendConfig {
  const normalized = {} as Record<PublicFrontendConfigKey, string | number>;

  for (const key of PUBLIC_FRONTEND_CONFIG_KEYS) {
    const fallback = DEFAULT_PUBLIC_FRONTEND_CONFIG[key];
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

    const parsed = JSON.parse(rawValue) as Partial<PublicFrontendConfig>;
    return extractPublicFrontendConfig(parsed);
  } catch {
    return cloneDefaultPublicFrontendConfig();
  }
}

export function savePublicFrontendConfig(
  source: Partial<PublicFrontendConfig>
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
  source?: Partial<PublicFrontendConfig>
): Record<string, string> {
  const normalized = source
    ? extractPublicFrontendConfig(source)
    : loadPublicFrontendConfig();

  return {
    ...buildAuthHeaders(),
    'X-Rag-Public-Config': JSON.stringify(normalized)
  };
}
