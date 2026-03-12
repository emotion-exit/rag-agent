<script setup lang="ts">
defineOptions({
  name: 'SettingsView'
});

import { computed, onMounted, reactive, ref } from 'vue';
import {
  CloudServerOutlined,
  DownOutlined,
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
const advancedExpanded = ref(false);

const healthText = computed(() => {
  if (health.value === 'online') return '后端服务运行中';
  if (health.value === 'restarting') return '正在重启本地知识库服务';
  if (health.value === 'offline') return '后端服务不可用';
  return '等待检测服务状态';
});

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

function toggleAdvanced() {
  advancedExpanded.value = !advancedExpanded.value;
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
        <h1 class="hero-title">本地服务配置</h1>
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
      <section class="settings-grid">
        <article class="panel-surface form-panel">
          <div class="panel-headline">能力配置</div>
          <div class="field-grid single-column-grid">
            <label class="field-block">
              <span class="field-label">对话 API Key</span>
              <input
                v-model="form.CHAT_API_KEY"
                class="field-input"
                type="password"
                placeholder="用于对话能力调用" />
              <span class="field-help">
                对话模型请求使用的密钥。具体由你接入的 LiteLLM
                后端或代理策略决定。
              </span>
            </label>

            <label class="field-block">
              <span class="field-label">对话 EndPoint</span>
              <input
                v-model="form.CHAT_BASE_URL"
                class="field-input"
                type="text"
                placeholder="例如 https://openrouter.ai/api/v1" />
              <span class="field-help">
                对话请求发送到的接口地址。由于底层走
                LiteLLM，这里不限定具体服务商。
              </span>
            </label>

            <label class="field-block">
              <span class="field-label">对话 Model</span>
              <input
                v-model="form.CHAT_MODEL"
                class="field-input"
                type="text"
                placeholder="例如 anthropic/claude-3-haiku" />
              <span class="field-help">
                对话能力使用的模型标识，格式由你的 LiteLLM 路由规则决定。
              </span>
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
              <span class="field-help">
                控制回答稳定性与发散度。值越低越稳，越高越灵活。
              </span>
            </label>

            <label class="field-block">
              <span class="field-label">嵌入 API Key</span>
              <input
                v-model="form.EMBEDDING_API_KEY"
                class="field-input"
                type="password"
                placeholder="用于嵌入能力调用" />
              <span class="field-help">
                文档分块和问题向量化所使用的密钥。可以与对话、重排分别使用不同提供商。
              </span>
            </label>

            <label class="field-block">
              <span class="field-label">嵌入 EndPoint</span>
              <input
                v-model="form.EMBEDDING_BASE_URL"
                class="field-input"
                type="text"
                placeholder="例如 https://api.siliconflow.cn/v1" />
              <span class="field-help">
                嵌入请求发送到的接口地址。可独立于重排和对话配置。
              </span>
            </label>

            <label class="field-block">
              <span class="field-label">嵌入 Model</span>
              <input
                v-model="form.EMBEDDING_MODEL"
                class="field-input"
                type="text"
                placeholder="BAAI/bge-large-zh-v1.5" />
              <span class="field-help">
                文档切片与问题向量化所使用的嵌入模型。
              </span>
            </label>

            <label class="field-block">
              <span class="field-label">重排 API Key</span>
              <input
                v-model="form.RERANKER_API_KEY"
                class="field-input"
                type="password"
                placeholder="用于重排能力调用" />
              <span class="field-help">
                候选片段二次排序所使用的密钥。需要与嵌入或对话分供应商时单独配置这里。
              </span>
            </label>

            <label class="field-block">
              <span class="field-label">重排 EndPoint</span>
              <input
                v-model="form.RERANKER_BASE_URL"
                class="field-input"
                type="text"
                placeholder="例如 https://api.siliconflow.cn/v1" />
              <span class="field-help">
                重排请求发送到的接口地址。可与嵌入完全不同。
              </span>
            </label>

            <label class="field-block">
              <span class="field-label">重排 Model</span>
              <input
                v-model="form.RERANKER_MODEL"
                class="field-input"
                type="text"
                placeholder="BAAI/bge-reranker-v2-m3" />
              <span class="field-help">
                用于对召回结果再次排序的模型，决定最终送进上下文窗口的片段优先级。
              </span>
            </label>
          </div>
        </article>

        <article class="panel-surface form-panel">
          <div class="panel-headline">运行维护</div>
          <div class="ops-stack">
            <p class="panel-copy">
              默认情况下只展示常用能力配置。目录、跨域和请求分类等低频参数放在高级设置里，避免干扰日常使用。
            </p>
            <button
              type="button"
              class="advanced-toggle"
              @click="toggleAdvanced">
              <span>高级设置</span>
              <DownOutlined
                :class="[
                  'advanced-arrow',
                  advancedExpanded ? 'expanded' : ''
                ]" />
            </button>

            <div
              v-if="advancedExpanded"
              class="field-grid single-column-grid advanced-grid">
              <label class="field-block">
                <span class="field-label">应用来源 URL</span>
                <input
                  v-model="form.OPENROUTER_SITE_URL"
                  class="field-input"
                  type="text"
                  placeholder="https://localhost.invalid" />
                <span class="field-help">
                  当对话接口实际接入 OpenRouter
                  时，用于标识请求来源；其他网关一般可以忽略。
                </span>
              </label>

              <label class="field-block">
                <span class="field-label">应用标识标题</span>
                <input
                  v-model="form.OPENROUTER_APP_TITLE"
                  class="field-input"
                  type="text"
                  placeholder="RAG.Agent Desktop" />
                <span class="field-help">
                  当上游网关需要记录请求来自哪个应用时使用。通常保持默认即可。
                </span>
              </label>

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
                <span class="field-help">
                  Chroma
                  持久化目录，保存向量索引与本地检索数据。只有在你想迁移或隔离数据时才需要修改。
                </span>
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
                <span class="field-help">
                  原始上传文档的存放目录。修改后适合把资料与应用程序分开管理。
                </span>
              </label>

              <label class="field-block">
                <span class="field-label">CORS Origins</span>
                <input
                  v-model="form.CORS_ORIGINS"
                  class="field-input"
                  type="text"
                  placeholder="http://localhost:5173,http://localhost:3000,null" />
                <span class="field-help">
                  允许访问本地后端的前端来源列表。桌面版一般无需修改，联调其他前端时再调整。
                </span>
              </label>

              <label class="field-block">
                <span class="field-label">OpenRouter Categories</span>
                <input
                  v-model="form.OPENROUTER_CATEGORIES"
                  class="field-input"
                  type="text"
                  placeholder="general-chat" />
                <span class="field-help">
                  请求附带的分类标记。仅在上游网关需要按类别统计、路由或审计时使用。
                </span>
              </label>
            </div>
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
  padding-bottom: 20px;
}

.panel-surface {
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(24, 24, 27, 0.06);
  box-shadow: 0 20px 50px rgba(24, 24, 27, 0.04);
  border-radius: 28px;
  padding: 28px;
}

.settings-hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
}

.eyebrow {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #71717a;
  font-weight: 700;
  margin-bottom: 12px;
}

.hero-title {
  margin: 0;
  font-size: 34px;
  line-height: 1.1;
  letter-spacing: -0.04em;
  color: #18181b;
}

.hero-copy {
  margin: 12px 0 0;
  max-width: 680px;
  line-height: 1.75;
  color: #71717a;
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
  color: #71717a;
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

.panel-headline {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #18181b;
}

.panel-copy {
  line-height: 1.7;
  color: #71717a;
}

.ops-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.advanced-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  min-height: 48px;
  padding: 0 16px;
  border-radius: 20px;
  border: 1px solid rgba(24, 24, 27, 0.08);
  background: linear-gradient(180deg, #fcfcfd 0%, #f5f5f5 100%);
  color: #3f3f46;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}

.advanced-toggle:hover {
  transform: translateY(-1px);
  border-color: rgba(24, 24, 27, 0.14);
}

.advanced-arrow {
  transition: transform 0.2s ease;
}

.advanced-arrow.expanded {
  transform: rotate(180deg);
}

.advanced-grid {
  padding-top: 6px;
}

.settings-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
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
  color: #3f3f46;
}

.field-help {
  font-size: 12px;
  line-height: 1.65;
  color: #71717a;
}

.field-input {
  width: 100%;
  min-height: 46px;
  border-radius: 16px;
  border: 1px solid rgba(24, 24, 27, 0.12);
  background: #fcfcfd;
  padding: 12px 14px;
  font-size: 14px;
  color: #18181b;
  outline: none;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}

.field-input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
  background: #ffffff;
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
  border-radius: 16px;
  padding: 0 16px;
  min-height: 46px;
  background: #f4f4f5;
  color: #3f3f46;
  font-weight: 600;
}

.primary-action {
  min-height: 48px;
  border-radius: 16px;
  padding: 0 20px;
  background: linear-gradient(135deg, #18181b, #27272a);
  color: #ffffff;
  font-weight: 700;
  box-shadow: 0 18px 36px rgba(24, 24, 27, 0.16);
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
