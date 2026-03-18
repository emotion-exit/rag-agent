import { contextBridge, ipcRenderer } from 'electron';

let backendStatus = ipcRenderer.sendSync('desktop:get-backend-status-sync');

if (!backendStatus || typeof backendStatus !== 'object') {
  backendStatus = {
    ready: false,
    apiBase: 'http://127.0.0.1:8765',
    state: 'idle',
    errorMessage: ''
  };
}

const backendStatusListeners = new Set();

ipcRenderer.on('desktop:backend-status', (_event, nextStatus) => {
  if (!nextStatus || typeof nextStatus !== 'object') {
    return;
  }

  backendStatus = nextStatus;
  for (const listener of backendStatusListeners) {
    listener(nextStatus);
  }
});

contextBridge.exposeInMainWorld('desktopApp', {
  isDesktop: true,
  apiBase: backendStatus.apiBase,
  platform: process.platform,
  getConfig: () => ipcRenderer.invoke('desktop:get-config'),
  saveConfig: (config) => ipcRenderer.invoke('desktop:save-config', config),
  getBackendStatus: () => ipcRenderer.invoke('desktop:get-backend-status'),
  restartBackend: () => ipcRenderer.invoke('desktop:restart-backend'),
  onBackendStatusChange: (listener) => {
    if (typeof listener !== 'function') {
      return () => {};
    }

    backendStatusListeners.add(listener);
    return () => {
      backendStatusListeners.delete(listener);
    };
  },
  pickDirectory: (currentPath) =>
    ipcRenderer.invoke('desktop:pick-directory', currentPath),
  openDataDirectory: () => ipcRenderer.invoke('desktop:open-data-directory')
});
