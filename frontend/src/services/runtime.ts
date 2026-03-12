export interface DesktopAppConfig {
  EMBEDDING_API_KEY: string;
  EMBEDDING_BASE_URL: string;
  EMBEDDING_MODEL: string;
  RERANKER_API_KEY: string;
  RERANKER_BASE_URL: string;
  RERANKER_MODEL: string;
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

const FALLBACK_API_BASE =
  import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export const DEFAULT_DESKTOP_CONFIG: DesktopAppConfig = {
  EMBEDDING_API_KEY: '',
  EMBEDDING_BASE_URL: '',
  EMBEDDING_MODEL: '',
  RERANKER_API_KEY: '',
  RERANKER_BASE_URL: '',
  RERANKER_MODEL: '',
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
