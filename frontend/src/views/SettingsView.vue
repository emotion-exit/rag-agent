<script setup lang="ts">
defineOptions({
  name: 'SettingsView'
});

import { computed, onMounted, reactive, ref } from 'vue';
import {
  CheckCircleOutlined,
  CloudServerOutlined,
  FolderOpenOutlined,
  ReloadOutlined,
  WarningOutlined
} from '@ant-design/icons-vue';
import {
  cloneDefaultDesktopConfig,
  getApiBase,
  isDesktopApp,
  type DesktopAppConfig
} from '@/services/runtime';

const isDesktop = isDesktopApp();
const apiBase = getApiBase();
const form = reactive<DesktopAppConfig>(cloneDefaultDesktopConfig());
const loading = ref(false);
const saving = ref(false);
const health = ref<'unknown' | 'online' | 'offline' | 'restarting'>('unknown');
const notice = ref<{ type: 'success' | 'error'; text: string } | null>(null);

const healthText = computed(() => {
  if (health.value === 'online') return '后端服务运行中';
  if (health.value === 'restarting') return '正在重启本地知识库服务';
  if (health.value === 'offline') return '后端服务不可用';
  return '等待检测服务状态';
});

const desktopHints = [
  '桌面版会在首次启动时自动生成本地配置文件，并把向量库与上传文件写入用户数据目录。',
  '保存配置后会自动重启内置 Python 服务，无需用户额外安装 Python、uv 或数据库。',
  'Windows 打包目标为 portable exe，macOS 打包目标为 dmg。'
];

async function refreshHealth() {
  if (!window.desktopApp) {
    health.value = 'offline';
    return;
  }

  try {
    const status = await window.desktopApp.getBackendStatus();
    if (!status.ready) {
      health.value = 'offline';
      return;
    }

    const response = await fetch(`${status.apiBase}/health`);
    health.value = response.ok ? 'online' : 'offline';
  } catch {
    health.value = 'offline';
  }
}

async function loadConfig() {
  if (!window.desktopApp) return;

  loading.value = true;
  notice.value = null;

  try {
    Object.assign(
      form,
      cloneDefaultDesktopConfig(),
      await window.desktopApp.getConfig()
    );
    await refreshHealth();
  } catch (error) {
    health.value = 'offline';
    notice.value = {
      type: 'error',
      text: error instanceof Error ? error.message : '读取本地配置失败。'
    };
  } finally {
    loading.value = false;
  }
}

async function saveConfig() {
  if (!window.desktopApp || saving.value) return;

  saving.value = true;
  health.value = 'restarting';
  notice.value = null;

  try {
    const saved = await window.desktopApp.saveConfig({ ...form });
    Object.assign(form, cloneDefaultDesktopConfig(), saved);
    notice.value = { type: 'success', text: '配置已保存，内置服务已重启。' };
    await refreshHealth();
  } catch (error) {
    health.value = 'offline';
    notice.value = {
      type: 'error',
      text: error instanceof Error ? error.message : '保存配置失败。'
    };
  } finally {
    saving.value = false;
  }
}

async function restartBackend() {
  if (!window.desktopApp) return;

  health.value = 'restarting';
  notice.value = null;

  try {
    await window.desktopApp.restartBackend();
    await refreshHealth();
    notice.value = { type: 'success', text: '本地服务已手动重启。' };
  } catch (error) {
    health.value = 'offline';
    notice.value = {
      type: 'error',
      text: error instanceof Error ? error.message : '重启本地服务失败。'
    };
  }
}

async function pickDirectory(field: 'CHROMA_PERSIST_DIR' | 'UPLOAD_DIR') {
  if (!window.desktopApp) return;

  const selected = await window.desktopApp.pickDirectory(form[field]);
  if (selected) {
    form[field] = selected;
  }
}

async function openDataDirectory() {
  await window.desktopApp?.openDataDirectory();
}

onMounted(() => {
  if (isDesktop) {
    loadConfig();
  }
});
</script>

<template>
  <div class="settings-page">
    <section class="settings-hero panel-surface">
      <div>
        <div class="eyebrow">Desktop Runtime</div>
        <h1 class="hero-title">桌面封装与本地服务配置</h1>
        <p class="hero-copy">
          当前桌面版采用 Electron + 内置 Python 后端 + 本地 Chroma
          存储。用户只需打开应用，无需额外安装运行时。
        </p>
      </div>
      <div class="hero-status">
        <div :class="['status-chip', `status-${health}`]">
          <CloudServerOutlined />
          <span>{{ healthText }}</span>
        </div>
        <div class="status-meta">API 地址：{{ apiBase }}</div>
      </div>
    </section>

    <section v-if="!isDesktop" class="panel-surface unsupported-panel">
      <WarningOutlined class="unsupported-icon" />
      <div>
        <h2>当前不是桌面环境</h2>
        <p>
          这个页面主要服务于 Electron
          打包版本。浏览器开发模式下仍然可以继续使用现有前后端联调流程。
        </p>
      </div>
    </section>

    <template v-else>
      <section class="panel-surface desktop-hints">
        <div class="panel-headline">交付形态</div>
        <div class="hint-list">
          <div v-for="hint in desktopHints" :key="hint" class="hint-item">
            <CheckCircleOutlined />
            <span>{{ hint }}</span>
          </div>
        </div>
      </section>

      <section class="settings-grid">
        <article class="panel-surface form-panel">
          <div class="panel-headline">模型与服务</div>
          <div class="field-grid">
            <label class="field-block field-span-2">
              <span class="field-label">OpenRouter API Key</span>
              <input
                v-model="form.OPENROUTER_API_KEY"
                class="field-input"
                type="password"
                placeholder="用于问答模型调用" />
            </label>

            <label class="field-block">
              <span class="field-label">对话模型</span>
              <input
                v-model="form.CHAT_MODEL"
                class="field-input"
                type="text"
                placeholder="例如 anthropic/claude-3-haiku" />
            </label>

            <label class="field-block">
              <span class="field-label">温度</span>
              <input
                v-model.number="form.CHAT_TEMPERATURE"
                class="field-input"
                type="number"
                min="0"
                max="1"
                step="0.1"
                placeholder="0.2" />
            </label>

            <label class="field-block">
              <span class="field-label">OpenRouter Base URL</span>
              <input
                v-model="form.OPENROUTER_BASE_URL"
                class="field-input"
                type="text"
                placeholder="https://openrouter.ai/api/v1" />
            </label>

            <label class="field-block field-span-2">
              <span class="field-label">SiliconFlow API Key</span>
              <input
                v-model="form.SILICONFLOW_API_KEY"
                class="field-input"
                type="password"
                placeholder="用于 embedding 与 rerank" />
            </label>

            <label class="field-block">
              <span class="field-label">Embedding 模型</span>
              <input
                v-model="form.EMBEDDING_MODEL"
                class="field-input"
                type="text"
                placeholder="BAAI/bge-large-zh-v1.5" />
            </label>

            <label class="field-block">
              <span class="field-label">Reranker 模型</span>
              <input
                v-model="form.RERANKER_MODEL"
                class="field-input"
                type="text"
                placeholder="BAAI/bge-reranker-v2-m3" />
            </label>

            <label class="field-block field-span-2">
              <span class="field-label">SiliconFlow Base URL</span>
              <input
                v-model="form.SILICONFLOW_BASE_URL"
                class="field-input"
                type="text"
                placeholder="https://api.siliconflow.cn/v1" />
            </label>

            <label class="field-block">
              <span class="field-label">应用标识标题</span>
              <input
                v-model="form.OPENROUTER_APP_TITLE"
                class="field-input"
                type="text"
                placeholder="RAG.Agent Desktop" />
            </label>

            <label class="field-block">
              <span class="field-label">应用来源 URL</span>
              <input
                v-model="form.OPENROUTER_SITE_URL"
                class="field-input"
                type="text"
                placeholder="https://localhost.invalid" />
            </label>
          </div>
        </article>

        <article class="panel-surface form-panel">
          <div class="panel-headline">本地数据</div>
          <div class="field-grid single-column-grid">
            <label class="field-block">
              <span class="field-label">向量库目录</span>
              <div class="path-input-wrap">
                <input
                  v-model="form.CHROMA_PERSIST_DIR"
                  class="field-input"
                  type="text"
                  placeholder="例如 ./data/chroma" />
                <button
                  type="button"
                  class="path-button"
                  @click="pickDirectory('CHROMA_PERSIST_DIR')">
                  <FolderOpenOutlined />
                  选择目录
                </button>
              </div>
            </label>

            <label class="field-block">
              <span class="field-label">上传文件目录</span>
              <div class="path-input-wrap">
                <input
                  v-model="form.UPLOAD_DIR"
                  class="field-input"
                  type="text"
                  placeholder="例如 ./data/uploads" />
                <button
                  type="button"
                  class="path-button"
                  @click="pickDirectory('UPLOAD_DIR')">
                  <FolderOpenOutlined />
                  选择目录
                </button>
              </div>
            </label>

            <label class="field-block">
              <span class="field-label">CORS Origins</span>
              <input
                v-model="form.CORS_ORIGINS"
                class="field-input"
                type="text"
                placeholder="http://localhost:5173,http://localhost:3000,null" />
            </label>

            <label class="field-block">
              <span class="field-label">OpenRouter Categories</span>
              <input
                v-model="form.OPENROUTER_CATEGORIES"
                class="field-input"
                type="text"
                placeholder="general-chat" />
            </label>
          </div>
        </article>
      </section>

      <section class="panel-surface action-panel">
        <div v-if="notice" :class="['notice-strip', `notice-${notice.type}`]">
          {{ notice.text }}
        </div>

        <div class="action-row">
          <button
            type="button"
            class="primary-action"
            :disabled="loading || saving"
            @click="saveConfig">
            {{ saving ? '正在保存并重启服务...' : '保存配置并重启服务' }}
          </button>
          <button
            type="button"
            class="secondary-action"
            :disabled="loading || saving"
            @click="restartBackend">
            <ReloadOutlined />
            手动重启服务
          </button>
          <button
            type="button"
            class="secondary-action"
            :disabled="loading || saving"
            @click="openDataDirectory">
            <FolderOpenOutlined />
            打开数据目录
          </button>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.settings-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-top: 20px;
}

.panel-surface {
  border-radius: 28px;
  background:
    linear-gradient(
      180deg,
      rgba(255, 255, 255, 0.92),
      rgba(249, 246, 239, 0.9)
    ),
    #ffffff;
  border: 1px solid rgba(120, 107, 74, 0.12);
  box-shadow: 0 24px 80px -44px rgba(91, 77, 46, 0.35);
  padding: 24px;
}

.settings-hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
}

.eyebrow {
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #8c6f3d;
  margin-bottom: 10px;
}

.hero-title {
  margin: 0;
  font-size: 30px;
  line-height: 1.1;
  color: #2b2418;
}

.hero-copy {
  margin: 12px 0 0;
  max-width: 680px;
  line-height: 1.7;
  color: #5f533d;
}

.hero-status {
  min-width: 240px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-end;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
}

.status-online {
  background: rgba(37, 99, 65, 0.12);
  color: #1f6b42;
}

.status-restarting,
.status-unknown {
  background: rgba(180, 125, 29, 0.12);
  color: #9f670f;
}

.status-offline {
  background: rgba(177, 55, 42, 0.12);
  color: #9e3328;
}

.status-meta {
  font-size: 13px;
  color: #77674a;
}

.unsupported-panel {
  display: flex;
  align-items: center;
  gap: 16px;
}

.unsupported-icon {
  font-size: 26px;
  color: #9e3328;
}

.desktop-hints {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.panel-headline {
  font-size: 16px;
  font-weight: 700;
  color: #2b2418;
}

.hint-list {
  display: grid;
  gap: 12px;
}

.hint-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  color: #564a35;
  line-height: 1.7;
}

.hint-item :deep(svg) {
  margin-top: 4px;
  color: #8c6f3d;
}

.settings-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.9fr);
  gap: 20px;
}

.form-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.single-column-grid {
  grid-template-columns: minmax(0, 1fr);
}

.field-span-2 {
  grid-column: span 2;
}

.field-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-label {
  font-size: 13px;
  font-weight: 600;
  color: #5f533d;
}

.field-input {
  width: 100%;
  min-height: 46px;
  border-radius: 14px;
  border: 1px solid rgba(120, 107, 74, 0.2);
  background: rgba(255, 255, 255, 0.94);
  padding: 0 14px;
  font-size: 14px;
  color: #2b2418;
  outline: none;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.field-input:focus {
  border-color: rgba(140, 111, 61, 0.8);
  box-shadow: 0 0 0 4px rgba(140, 111, 61, 0.12);
}

.path-input-wrap {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
}

.path-button,
.secondary-action,
.primary-action {
  border: none;
  cursor: pointer;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    opacity 0.18s ease;
}

.path-button,
.secondary-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: 14px;
  padding: 0 16px;
  min-height: 46px;
  background: rgba(140, 111, 61, 0.1);
  color: #5b4f37;
  font-weight: 600;
}

.primary-action {
  min-height: 48px;
  border-radius: 16px;
  padding: 0 20px;
  background: linear-gradient(135deg, #8c6f3d, #b98d42);
  color: #fffdf8;
  font-weight: 700;
  box-shadow: 0 18px 40px -22px rgba(140, 111, 61, 0.7);
}

.path-button:hover,
.secondary-action:hover,
.primary-action:hover {
  transform: translateY(-1px);
}

.path-button:disabled,
.secondary-action:disabled,
.primary-action:disabled {
  cursor: not-allowed;
  opacity: 0.6;
  transform: none;
}

.action-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.notice-strip {
  border-radius: 16px;
  padding: 14px 16px;
  font-size: 14px;
}

.notice-success {
  background: rgba(37, 99, 65, 0.12);
  color: #1f6b42;
}

.notice-error {
  background: rgba(177, 55, 42, 0.12);
  color: #9e3328;
}

@media (max-width: 960px) {
  .settings-hero,
  .settings-grid {
    grid-template-columns: 1fr;
    display: grid;
  }

  .hero-status {
    align-items: flex-start;
    min-width: auto;
  }
}

@media (max-width: 768px) {
  .panel-surface {
    padding: 18px;
    border-radius: 22px;
  }

  .hero-title {
    font-size: 24px;
  }

  .field-grid,
  .path-input-wrap {
    grid-template-columns: 1fr;
  }

  .field-span-2 {
    grid-column: span 1;
  }

  .action-row {
    flex-direction: column;
  }
}
</style>
