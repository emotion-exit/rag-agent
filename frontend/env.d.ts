/// <reference types="vite/client" />

interface DesktopAppConfig {
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

interface DesktopBackendStatus {
  ready: boolean;
  apiBase: string;
  state?: 'idle' | 'starting' | 'ready' | 'error';
  errorMessage?: string;
}

interface DesktopAppBridge {
  isDesktop: boolean;
  apiBase: string;
  platform: string;
  getConfig: () => Promise<DesktopAppConfig>;
  saveConfig: (config: DesktopAppConfig) => Promise<DesktopAppConfig>;
  getBackendStatus: () => Promise<DesktopBackendStatus>;
  restartBackend: () => Promise<DesktopBackendStatus>;
  onBackendStatusChange: (
    listener: (status: DesktopBackendStatus) => void
  ) => () => void;
  pickDirectory: (currentPath?: string) => Promise<string | null>;
  openDataDirectory: () => Promise<void>;
}

interface Window {
  desktopApp?: DesktopAppBridge;
}

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
}
