export interface DesktopAppConfig {
  EMBEDDING_API_KEY: string;
  EMBEDDING_BASE_URL: string;
  EMBEDDING_MODEL: string;
  EMBEDDING_PROVIDER: string;
  EMBEDDING_MAX_INPUT_TOKENS: number;
  EMBEDDING_TARGET_CHUNK_TOKENS: number;
  EMBEDDING_CHUNK_OVERLAP_TOKENS: number;
  EMBEDDING_TOKENIZER_MODEL: string;
  EMBEDDING_TOKENIZER_ENCODING: string;
  RERANKER_API_KEY: string;
  RERANKER_BASE_URL: string;
  RERANKER_MODEL: string;
  RERANKER_REQUEST_TIMEOUT: number;
  RETRIEVAL_CANDIDATE_LIMIT: number;
  RETRIEVAL_FINAL_CONTEXT_LIMIT: number;
  RETRIEVAL_SOURCE_LIMIT: number;
  RETRIEVAL_QUERY_EXPANSION_COUNT: number;
  CHAT_API_KEY: string;
  CHAT_BASE_URL: string;
  CHAT_MODEL: string;
  CHAT_TEMPERATURE: number;
  OPENROUTER_SITE_URL: string;
  OPENROUTER_APP_TITLE: string;
  OPENROUTER_CATEGORIES: string;
  CHROMA_PERSIST_DIR: string;
  UPLOAD_DIR: string;
  CORS_ORIGINS: string;
}

const DESKTOP_REQUIRED_CONFIG_FIELDS = [
  'EMBEDDING_API_KEY',
  'EMBEDDING_BASE_URL',
  'EMBEDDING_MODEL',
  'RERANKER_API_KEY',
  'RERANKER_BASE_URL',
  'RERANKER_MODEL',
  'CHAT_API_KEY',
  'CHAT_BASE_URL',
  'CHAT_MODEL'
] as const satisfies readonly (keyof DesktopAppConfig)[];

const FALLBACK_API_BASE =
  import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export const DEFAULT_DESKTOP_CONFIG: DesktopAppConfig = {
  EMBEDDING_API_KEY: '',
  EMBEDDING_BASE_URL: '',
  EMBEDDING_MODEL: '',
  EMBEDDING_PROVIDER: 'openai',
  EMBEDDING_MAX_INPUT_TOKENS: 512,
  EMBEDDING_TARGET_CHUNK_TOKENS: 384,
  EMBEDDING_CHUNK_OVERLAP_TOKENS: 48,
  EMBEDDING_TOKENIZER_MODEL: '',
  EMBEDDING_TOKENIZER_ENCODING: 'cl100k_base',
  RERANKER_API_KEY: '',
  RERANKER_BASE_URL: '',
  RERANKER_MODEL: '',
  RERANKER_REQUEST_TIMEOUT: 20,
  RETRIEVAL_CANDIDATE_LIMIT: 10,
  RETRIEVAL_FINAL_CONTEXT_LIMIT: 3,
  RETRIEVAL_SOURCE_LIMIT: 3,
  RETRIEVAL_QUERY_EXPANSION_COUNT: 2,
  CHAT_API_KEY: '',
  CHAT_BASE_URL: '',
  CHAT_MODEL: '',
  CHAT_TEMPERATURE: 0,
  OPENROUTER_SITE_URL: 'https://localhost.invalid',
  OPENROUTER_APP_TITLE: 'RAG.Agent Desktop',
  OPENROUTER_CATEGORIES: 'general-chat',
  CHROMA_PERSIST_DIR: './data/chroma',
  UPLOAD_DIR: './data/uploads',
  CORS_ORIGINS: 'http://localhost:5173,http://localhost:3000,null'
};

export function isDesktopApp() {
  return Boolean(window.desktopApp?.isDesktop);
}

export function getApiBase() {
  return window.desktopApp?.apiBase || FALLBACK_API_BASE;
}

export function cloneDefaultDesktopConfig(): DesktopAppConfig {
  return { ...DEFAULT_DESKTOP_CONFIG };
}

export function hasRequiredDesktopProviderConfig(
  source: Partial<DesktopAppConfig>
) {
  return DESKTOP_REQUIRED_CONFIG_FIELDS.every((field) => {
    const value = source[field];
    return typeof value === 'string' && value.trim().length > 0;
  });
}

export async function shouldRedirectToSettingsOnDesktop() {
  if (!isDesktopApp() || !window.desktopApp) {
    return false;
  }

  try {
    const config = await window.desktopApp.getConfig();
    return !hasRequiredDesktopProviderConfig(config);
  } catch {
    return false;
  }
}
