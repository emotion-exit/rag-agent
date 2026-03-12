import { contextBridge, ipcRenderer } from 'electron';

const apiBase = 'http://127.0.0.1:8765';

contextBridge.exposeInMainWorld('desktopApp', {
  isDesktop: true,
  apiBase,
  platform: process.platform,
  getConfig: () => ipcRenderer.invoke('desktop:get-config'),
  saveConfig: (config) => ipcRenderer.invoke('desktop:save-config', config),
  getBackendStatus: () => ipcRenderer.invoke('desktop:get-backend-status'),
  restartBackend: () => ipcRenderer.invoke('desktop:restart-backend'),
  pickDirectory: (currentPath) =>
    ipcRenderer.invoke('desktop:pick-directory', currentPath),
  openDataDirectory: () => ipcRenderer.invoke('desktop:open-data-directory')
});
