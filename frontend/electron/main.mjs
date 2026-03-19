import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import net from 'node:net';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  nativeImage,
  shell
} from 'electron';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DEFAULT_API_HOST = '127.0.0.1';
const DEFAULT_API_PORT = 8765;
const MAX_PORT_SCAN_ATTEMPTS = 20;
const isWindows = process.platform === 'win32';
const allowedConfigKeys = [
  'EMBEDDING_API_KEY',
  'EMBEDDING_BASE_URL',
  'EMBEDDING_MODEL',
  'EMBEDDING_PROVIDER',
  'EMBEDDING_MAX_INPUT_TOKENS',
  'EMBEDDING_TARGET_CHUNK_TOKENS',
  'EMBEDDING_CHUNK_OVERLAP_TOKENS',
  'EMBEDDING_TOKENIZER_MODEL',
  'EMBEDDING_TOKENIZER_ENCODING',
  'RERANKER_API_KEY',
  'RERANKER_BASE_URL',
  'RERANKER_MODEL',
  'RERANKER_REQUEST_TIMEOUT',
  'RETRIEVAL_CANDIDATE_LIMIT',
  'RETRIEVAL_FINAL_CONTEXT_LIMIT',
  'RETRIEVAL_SOURCE_LIMIT',
  'RETRIEVAL_QUERY_EXPANSION_COUNT',
  'CHAT_API_KEY',
  'CHAT_BASE_URL',
  'CHAT_MODEL',
  'CHAT_TEMPERATURE',
  'OPENROUTER_SITE_URL',
  'OPENROUTER_APP_TITLE',
  'OPENROUTER_CATEGORIES',
  'CHROMA_PERSIST_DIR',
  'UPLOAD_DIR',
  'CORS_ORIGINS'
];

let mainWindow = null;
let backendProcess = null;
let backendReady = false;
let backendState = 'idle';
let backendErrorMessage = '';
let backendStopExpected = false;
let currentApiHost = DEFAULT_API_HOST;
let currentApiPort = DEFAULT_API_PORT;

function getApiBase() {
  return `http://${currentApiHost}:${currentApiPort}`;
}

function emitBackendStatusChanged() {
  mainWindow?.webContents.send(
    'desktop:backend-status',
    getBackendStatusSnapshot()
  );
}

function getBackendStatusSnapshot() {
  return {
    ready: backendReady,
    apiBase: getApiBase(),
    state: backendState,
    errorMessage: backendErrorMessage
  };
}

function updateBackendStatus(nextState, nextErrorMessage = '') {
  backendState = nextState;
  backendErrorMessage = nextErrorMessage;
  emitBackendStatusChanged();
}

async function findAvailablePort(host, preferredPort) {
  const tryPort = (port) =>
    new Promise((resolve, reject) => {
      const server = net.createServer();

      server.once('error', (error) => {
        server.close();
        reject(error);
      });

      server.once('listening', () => {
        const address = server.address();
        const resolvedPort =
          address && typeof address === 'object' ? address.port : port;
        server.close(() => resolve(resolvedPort));
      });

      server.listen(port, host);
    });

  for (let attempt = 0; attempt < MAX_PORT_SCAN_ATTEMPTS; attempt += 1) {
    const candidatePort = preferredPort + attempt;

    try {
      return await tryPort(candidatePort);
    } catch (error) {
      if (error && typeof error === 'object' && error.code === 'EADDRINUSE') {
        continue;
      }

      throw error;
    }
  }

  return await tryPort(0);
}

function getMacDockIconPath() {
  const macDockIconPath = join(__dirname, './assets/icon.png');
  return existsSync(macDockIconPath) ? macDockIconPath : null;
}

function getDesktopIconPath() {
  if (process.platform === 'darwin') {
    const macIconPath = join(__dirname, './assets/icon.icns');
    if (existsSync(macIconPath)) {
      return macIconPath;
    }
  }

  const iconPath = join(__dirname, './assets/icon.png');
  return existsSync(iconPath) ? iconPath : null;
}

function getConfigPath() {
  return join(app.getPath('userData'), 'config.json');
}

function createDefaultConfig() {
  return {
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
    RETRIEVAL_CANDIDATE_LIMIT: 18,
    RETRIEVAL_FINAL_CONTEXT_LIMIT: 5,
    RETRIEVAL_SOURCE_LIMIT: 5,
    RETRIEVAL_QUERY_EXPANSION_COUNT: 3,
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
}

function normalizeTemperature(value) {
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return createDefaultConfig().CHAT_TEMPERATURE;
  }

  return Math.min(1, Math.max(0, numeric));
}

function normalizePositiveNumber(value, fallback) {
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return fallback;
  }

  return numeric;
}

function normalizePositiveInteger(value, fallback) {
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return fallback;
  }

  return Math.max(1, Math.round(numeric));
}

function normalizeNonNegativeInteger(value, fallback) {
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric) || numeric < 0) {
    return fallback;
  }

  return Math.max(0, Math.round(numeric));
}

async function ensureDesktopConfig() {
  const configPath = getConfigPath();
  await mkdir(dirname(configPath), { recursive: true });

  if (!existsSync(configPath)) {
    await writeFile(
      configPath,
      `${JSON.stringify(createDefaultConfig(), null, 2)}\n`,
      'utf-8'
    );
  }

  return configPath;
}

async function readDesktopConfig() {
  const configPath = await ensureDesktopConfig();
  const content = await readFile(configPath, 'utf-8');
  const parsed = JSON.parse(content);
  const merged = {
    ...createDefaultConfig(),
    ...(parsed && typeof parsed === 'object' ? parsed : {})
  };

  merged.CHAT_TEMPERATURE = normalizeTemperature(merged.CHAT_TEMPERATURE);
  merged.EMBEDDING_MAX_INPUT_TOKENS = normalizePositiveInteger(
    merged.EMBEDDING_MAX_INPUT_TOKENS,
    createDefaultConfig().EMBEDDING_MAX_INPUT_TOKENS
  );
  merged.EMBEDDING_TARGET_CHUNK_TOKENS = normalizePositiveInteger(
    merged.EMBEDDING_TARGET_CHUNK_TOKENS,
    createDefaultConfig().EMBEDDING_TARGET_CHUNK_TOKENS
  );
  merged.EMBEDDING_CHUNK_OVERLAP_TOKENS = normalizeNonNegativeInteger(
    merged.EMBEDDING_CHUNK_OVERLAP_TOKENS,
    createDefaultConfig().EMBEDDING_CHUNK_OVERLAP_TOKENS
  );
  merged.RERANKER_REQUEST_TIMEOUT = normalizePositiveNumber(
    merged.RERANKER_REQUEST_TIMEOUT,
    createDefaultConfig().RERANKER_REQUEST_TIMEOUT
  );
  merged.RETRIEVAL_CANDIDATE_LIMIT = normalizePositiveInteger(
    merged.RETRIEVAL_CANDIDATE_LIMIT,
    createDefaultConfig().RETRIEVAL_CANDIDATE_LIMIT
  );
  merged.RETRIEVAL_FINAL_CONTEXT_LIMIT = normalizePositiveInteger(
    merged.RETRIEVAL_FINAL_CONTEXT_LIMIT,
    createDefaultConfig().RETRIEVAL_FINAL_CONTEXT_LIMIT
  );
  merged.RETRIEVAL_SOURCE_LIMIT = normalizePositiveInteger(
    merged.RETRIEVAL_SOURCE_LIMIT,
    createDefaultConfig().RETRIEVAL_SOURCE_LIMIT
  );
  merged.RETRIEVAL_QUERY_EXPANSION_COUNT = normalizeNonNegativeInteger(
    merged.RETRIEVAL_QUERY_EXPANSION_COUNT,
    createDefaultConfig().RETRIEVAL_QUERY_EXPANSION_COUNT
  );
  return merged;
}

async function writeDesktopConfig(nextConfig) {
  const configPath = await ensureDesktopConfig();
  const sanitized = createDefaultConfig();

  for (const key of allowedConfigKeys) {
    const value = nextConfig?.[key];
    if (typeof value === 'string') {
      sanitized[key] = value;
      continue;
    }

    if (key === 'CHAT_TEMPERATURE') {
      sanitized[key] = normalizeTemperature(value);
      continue;
    }

    if (key === 'EMBEDDING_MAX_INPUT_TOKENS') {
      sanitized[key] = normalizePositiveInteger(
        value,
        createDefaultConfig().EMBEDDING_MAX_INPUT_TOKENS
      );
      continue;
    }

    if (key === 'EMBEDDING_TARGET_CHUNK_TOKENS') {
      sanitized[key] = normalizePositiveInteger(
        value,
        createDefaultConfig().EMBEDDING_TARGET_CHUNK_TOKENS
      );
      continue;
    }

    if (key === 'EMBEDDING_CHUNK_OVERLAP_TOKENS') {
      sanitized[key] = normalizeNonNegativeInteger(
        value,
        createDefaultConfig().EMBEDDING_CHUNK_OVERLAP_TOKENS
      );
      continue;
    }

    if (key === 'RERANKER_REQUEST_TIMEOUT') {
      sanitized[key] = normalizePositiveNumber(
        value,
        createDefaultConfig().RERANKER_REQUEST_TIMEOUT
      );
      continue;
    }

    if (key === 'RETRIEVAL_CANDIDATE_LIMIT') {
      sanitized[key] = normalizePositiveInteger(
        value,
        createDefaultConfig().RETRIEVAL_CANDIDATE_LIMIT
      );
      continue;
    }

    if (key === 'RETRIEVAL_FINAL_CONTEXT_LIMIT') {
      sanitized[key] = normalizePositiveInteger(
        value,
        createDefaultConfig().RETRIEVAL_FINAL_CONTEXT_LIMIT
      );
      continue;
    }

    if (key === 'RETRIEVAL_SOURCE_LIMIT') {
      sanitized[key] = normalizePositiveInteger(
        value,
        createDefaultConfig().RETRIEVAL_SOURCE_LIMIT
      );
      continue;
    }

    if (key === 'RETRIEVAL_QUERY_EXPANSION_COUNT') {
      sanitized[key] = normalizeNonNegativeInteger(
        value,
        createDefaultConfig().RETRIEVAL_QUERY_EXPANSION_COUNT
      );
      continue;
    }
  }

  await writeFile(
    configPath,
    `${JSON.stringify(sanitized, null, 2)}\n`,
    'utf-8'
  );
  return sanitized;
}

function getBackendEnv(configPath) {
  return {
    ...process.env,
    APP_CONFIG_PATH: configPath,
    BACKEND_HOST: currentApiHost,
    BACKEND_PORT: String(currentApiPort)
  };
}

function getPackagedBackendExecutable() {
  const extension = isWindows ? '.exe' : '';
  return join(
    process.resourcesPath,
    'backend',
    `rag-agent-backend${extension}`
  );
}

function spawnBackendProcess(configPath) {
  if (app.isPackaged) {
    const executable = getPackagedBackendExecutable();
    return spawn(executable, [], {
      cwd: dirname(executable),
      env: getBackendEnv(configPath),
      stdio: 'ignore',
      windowsHide: true
    });
  }

  return spawn('uv', ['run', 'python', 'run_desktop.py'], {
    cwd: join(__dirname, '../../backend'),
    env: getBackendEnv(configPath),
    stdio: 'inherit',
    windowsHide: true
  });
}

async function waitForBackend(timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${getApiBase()}/health`);
      if (response.ok) {
        return true;
      }
    } catch {
      // Ignore startup polling errors.
    }

    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  throw new Error('内置后端启动超时，请检查模型配置或端口占用情况。');
}

async function stopBackend() {
  if (!backendProcess?.pid) {
    backendProcess = null;
    backendReady = false;
    updateBackendStatus('idle');
    return;
  }

  const pid = backendProcess.pid;
  backendStopExpected = true;
  backendReady = false;

  if (isWindows) {
    await new Promise((resolve) => {
      const killer = spawn('taskkill', ['/pid', String(pid), '/t', '/f'], {
        windowsHide: true,
        stdio: 'ignore'
      });
      killer.on('exit', resolve);
      killer.on('error', resolve);
    });
  } else {
    backendProcess.kill('SIGTERM');
  }

  backendProcess = null;
  updateBackendStatus('idle');
}

async function startBackend() {
  if (backendReady) {
    return getBackendStatusSnapshot();
  }

  await stopBackend();
  currentApiPort = await findAvailablePort(currentApiHost, currentApiPort);
  updateBackendStatus('starting');

  const configPath = await ensureDesktopConfig();
  backendProcess = spawnBackendProcess(configPath);
  backendStopExpected = false;

  backendProcess.once('exit', () => {
    if (backendStopExpected) {
      backendStopExpected = false;
      return;
    }

    const message = backendReady
      ? '服务已退出，请在设置页重试。'
      : '服务启动失败，请检查配置或端口占用。';
    backendReady = false;
    backendProcess = null;
    updateBackendStatus('error', message);
  });

  try {
    await waitForBackend();
    backendReady = true;
    updateBackendStatus('ready');
    return getBackendStatusSnapshot();
  } catch (error) {
    await stopBackend();
    updateBackendStatus(
      'error',
      error instanceof Error
        ? error.message
        : '服务启动失败，请检查配置或端口占用。'
    );
    throw error;
  }
}

async function restartBackend() {
  await stopBackend();
  return startBackend();
}

async function createMainWindow() {
  const iconPath = getDesktopIconPath();

  mainWindow = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 1180,
    minHeight: 760,
    backgroundColor: '#ffffff',
    show: false,
    title: 'RAG.Agent',
    ...(iconPath ? { icon: iconPath } : {}),
    webPreferences: {
      preload: join(__dirname, 'preload.mjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  if (process.env.VITE_DEV_SERVER_URL) {
    await mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    await mainWindow.loadFile(join(__dirname, '../dist/index.html'));
  }
}

ipcMain.handle('desktop:get-config', async () => readDesktopConfig());
ipcMain.handle('desktop:save-config', async (_event, nextConfig) => {
  const saved = await writeDesktopConfig(nextConfig);
  await restartBackend();
  return saved;
});
ipcMain.handle('desktop:get-backend-status', async () => ({
  ...getBackendStatusSnapshot()
}));
ipcMain.on('desktop:get-backend-status-sync', (event) => {
  event.returnValue = getBackendStatusSnapshot();
});
ipcMain.handle('desktop:restart-backend', async () => restartBackend());
ipcMain.handle('desktop:pick-directory', async (_event, currentPath) => {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory', 'createDirectory'],
    defaultPath:
      typeof currentPath === 'string' && currentPath.trim()
        ? currentPath
        : app.getPath('documents')
  });

  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }

  return result.filePaths[0];
});
ipcMain.handle('desktop:open-data-directory', async () => {
  await ensureDesktopConfig();
  await shell.openPath(app.getPath('userData'));
});

app.whenReady().then(async () => {
  try {
    const dockIconPath = getMacDockIconPath();
    if (process.platform === 'darwin' && dockIconPath) {
      app.dock.setIcon(nativeImage.createFromPath(dockIconPath));
    }

    await createMainWindow();
    startBackend().catch(() => {
      // Renderer polls backend status and will surface the failure state.
    });
  } catch (error) {
    dialog.showErrorBox(
      'RAG.Agent 启动失败',
      error instanceof Error ? error.message : '内置后端启动失败。'
    );
    app.quit();
    return;
  }

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await createMainWindow();
    }

    if (!backendReady && backendState !== 'starting') {
      startBackend().catch(() => {
        // Renderer polls backend status and will surface the failure state.
      });
    }
  });
});

app.on('before-quit', async () => {
  await stopBackend();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
