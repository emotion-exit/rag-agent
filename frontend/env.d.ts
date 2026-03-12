/// <reference types="vite/client" />

interface DesktopAppConfig {
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

interface DesktopBackendStatus {
  ready: boolean;
  apiBase: string;
}

interface DesktopAppBridge {
  isDesktop: boolean;
  apiBase: string;
  platform: string;
  getConfig: () => Promise<DesktopAppConfig>;
  saveConfig: (config: DesktopAppConfig) => Promise<DesktopAppConfig>;
  getBackendStatus: () => Promise<DesktopBackendStatus>;
  restartBackend: () => Promise<DesktopBackendStatus>;
  pickDirectory: (currentPath?: string) => Promise<string | null>;
  openDataDirectory: () => Promise<void>;
}

interface Window {
  desktopApp?: DesktopAppBridge;
}

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
}
