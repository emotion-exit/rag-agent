<script setup lang="ts">
defineOptions({
  name: 'SettingsView'
});

import { computed, onMounted, reactive, ref } from 'vue';
import {
  CheckCircleOutlined,
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
import {
  buildPublicConfigHeaders,
  loadPublicFrontendConfig,
  resetPublicFrontendConfig,
  savePublicFrontendConfig
} from '@/services/publicConfig';

const isDesktop = isDesktopApp();
const apiBase = getApiBase();
const form = reactive<DesktopAppConfig>(cloneDefaultDesktopConfig());
const loading = ref(false);
const saving = ref(false);
const health = ref<'unknown' | 'online' | 'offline' | 'restarting'>('unknown');
const notice = ref<{ type: 'success' | 'error'; text: string } | null>(null);
const advancedExpanded = ref(!isDesktop);
const providerHealthLoading = ref(false);
const providerHealth = ref<Record<string, ProviderHealthItem>>({});

interface ProviderHealthItem {
  status: string;
  configured: boolean;
  message?: string;
  detail?: string;
  base_url: string;
  model: string;
  provider?: string;
  probe_mode?: string;
  token_usage?: string;
  http_status?: number;
}

interface ProviderHealthResponse {
  status: string;
  providers?: Record<string, ProviderHealthItem>;
}

interface AdvancedSettingGroup {
  key: string;
  title: string;
  description: string;
}

const advancedSettingGroups: AdvancedSettingGroup[] = [
  {
    key: 'request-metadata',
    title: '请求元信息',
    description:
      '用于向上游网关传递应用来源、应用名称与请求标签等非敏感元信息。'
  },
  {
    key: 'embedding-strategy',
    title: 'Embedding 策略',
    description: '控制向量化 provider、token 统计方式与切分上限。'
  },
  {
    key: 'retrieval-strategy',
    title: '检索策略',
    description: '控制召回、重排、上下文保留与问题扩写数量。'
  },
  {
    key: 'storage-runtime',
    title: '存储与运行时',
    description: '控制本地目录与跨域来源等运行环境参数。'
  }
];
const requestMetadataGroup = advancedSettingGroups[0]!;
const embeddingStrategyGroup = advancedSettingGroups[1]!;
const retrievalStrategyGroup = advancedSettingGroups[2]!;
const storageRuntimeGroup = advancedSettingGroups[3]!;

const healthText = computed(() => {
  if (health.value === 'online') return '后端服务运行中';
  if (health.value === 'restarting') return '正在重启本地知识库服务';
  if (health.value === 'offline') return '后端服务不可用';
  return '等待检测服务状态';
});

const providerEntries = computed(() => {
  return [
    {
      key: 'embedding',
      title: 'Embedding',
      item: providerHealth.value.embedding
    },
    { key: 'reranker', title: 'Reranker', item: providerHealth.value.reranker },
    { key: 'chat', title: 'Chat', item: providerHealth.value.chat }
  ];
});

function getProviderStateLabel(status: string) {
  if (status === 'ok') return '连接正常';
  if (status === 'missing_config') return '缺少配置';
  if (status === 'auth_error') return '鉴权失败';
  if (status === 'timeout') return '请求超时';
  if (status === 'network_error') return '网络异常';
  if (status === 'upstream_error') return '上游异常';
  return '待检测';
}

function getProviderCardClass(status: string) {
  if (status === 'ok') return 'provider-card-ok';
  if (status === 'missing_config') return 'provider-card-missing';
  if (status === 'auth_error') return 'provider-card-error';
  return 'provider-card-warning';
}

function formatProviderLabel(provider?: string) {
  if (!provider) return '未标记';
  if (provider === 'openai' || provider === 'openai-compatible') {
    return 'OpenAI 兼容接口';
  }
  return provider;
}

function formatProbeMode(mode?: string) {
  if (!mode) return '未执行检测';
  if (mode === 'http_get_models') return 'GET /models 轻量探测';
  if (mode === 'http_post_embeddings') return 'POST /embeddings 实探';
  if (mode === 'http_post_rerank') return 'POST /rerank 实探';
  if (mode === 'missing_config') return '配置检查';
  return mode;
}

function formatTokenUsage(tokenUsage?: string) {
  if (!tokenUsage) return '未知';
  if (tokenUsage === 'none_expected') return '默认不消耗 token';
  if (tokenUsage === 'minimal_embedding_probe') return '极少量 embedding token';
  if (tokenUsage === 'minimal_rerank_probe') return '极少量 rerank token';
  return tokenUsage;
}

async function resolveBackendApiBase() {
  if (!window.desktopApp) {
    return apiBase;
  }

  const status = await window.desktopApp.getBackendStatus();
  return status.apiBase || apiBase;
}

async function refreshHealth() {
  if (!window.desktopApp) {
    try {
      const response = await fetch(`${apiBase}/health/public`, {
        headers: buildPublicConfigHeaders(form)
      });
      health.value = response.ok ? 'online' : 'offline';
    } catch {
      health.value = 'offline';
    }
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

async function checkProviderHealth(options?: { silent?: boolean }) {
  providerHealthLoading.value = true;

  try {
    const backendApiBase = await resolveBackendApiBase();
    const response = await fetch(
      `${backendApiBase}${isDesktop ? '/health/providers' : '/health/providers/public'}`,
      isDesktop
        ? undefined
        : {
            headers: buildPublicConfigHeaders(form)
          }
    );
    const data = (await response.json()) as ProviderHealthResponse;

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    providerHealth.value = data.providers || {};
    if (!options?.silent) {
      notice.value = { type: 'success', text: 'Provider 连接检测完成。' };
    }
  } catch (error) {
    providerHealth.value = {};
    if (!options?.silent) {
      notice.value = {
        type: 'error',
        text: error instanceof Error ? error.message : 'Provider 连接检测失败。'
      };
    }
  } finally {
    providerHealthLoading.value = false;
  }
}

async function loadConfig() {
  loading.value = true;
  notice.value = null;

  try {
    if (window.desktopApp) {
      Object.assign(
        form,
        cloneDefaultDesktopConfig(),
        await window.desktopApp.getConfig()
      );
      await refreshHealth();
      await checkProviderHealth({ silent: true });
    } else {
      Object.assign(
        form,
        cloneDefaultDesktopConfig(),
        loadPublicFrontendConfig()
      );
      await refreshHealth();
      await checkProviderHealth({ silent: true });
    }
  } catch (error) {
    health.value = isDesktop ? 'offline' : 'unknown';
    notice.value = {
      type: 'error',
      text: error instanceof Error ? error.message : '读取配置失败。'
    };
  } finally {
    loading.value = false;
  }
}

async function saveConfig() {
  if (saving.value) return;

  saving.value = true;
  notice.value = null;

  try {
    if (window.desktopApp) {
      health.value = 'restarting';
      const saved = await window.desktopApp.saveConfig({ ...form });
      Object.assign(form, cloneDefaultDesktopConfig(), saved);
      notice.value = { type: 'success', text: '配置已保存，内置服务已重启。' };
      await refreshHealth();
      await checkProviderHealth({ silent: true });
    } else {
      Object.assign(
        form,
        cloneDefaultDesktopConfig(),
        savePublicFrontendConfig(form)
      );
      await refreshHealth();
      await checkProviderHealth({ silent: true });
      notice.value = {
        type: 'success',
        text: '浏览器公开设置已保存，新的请求将自动使用这些参数。'
      };
    }
  } catch (error) {
    health.value = isDesktop ? 'offline' : 'unknown';
    notice.value = {
      type: 'error',
      text: error instanceof Error ? error.message : '保存配置失败。'
    };
  } finally {
    saving.value = false;
  }
}

function resetWebConfig() {
  if (window.desktopApp || saving.value) return;

  Object.assign(form, cloneDefaultDesktopConfig(), resetPublicFrontendConfig());
  refreshHealth();
  checkProviderHealth({ silent: true });
  notice.value = {
    type: 'success',
    text: '浏览器公开设置已恢复默认值。'
  };
}

async function restartBackend() {
  if (!window.desktopApp) return;

  health.value = 'restarting';
  notice.value = null;

  try {
    await window.desktopApp.restartBackend();
    await refreshHealth();
    await checkProviderHealth({ silent: true });
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
  loadConfig();
});
</script>

<template>
  <div class="settings-page">
    <section class="settings-hero panel-surface">
      <div>
        <div class="eyebrow">
          {{ isDesktop ? 'Desktop Runtime' : 'Web Runtime' }}
        </div>
        <h1 class="hero-title">
          {{ isDesktop ? '本地服务配置' : '公开高级设置' }}
        </h1>
        <p class="hero-copy">
          {{
            isDesktop
              ? '桌面端可配置完整运行参数；敏感 API 凭据仍保存在本地环境。'
              : 'Web 端对用户开放公开高级设置，配置保存在当前浏览器，并会随请求发送给后端；基础 API 配置不会在前端暴露。'
          }}
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
        <h2>当前为 Web 公开设置模式</h2>
        <p>
          当前页面对 Web 用户开放，但仅显示不会泄露凭据的高级设置。基础 API
          Key、Base URL 与 Model 仍由服务端或桌面端托管。
        </p>
      </div>
    </section>

    <section class="settings-grid">
      <article v-if="isDesktop" class="panel-surface form-panel">
        <div class="panel-headline">能力配置</div>
        <div class="field-grid multi-column-grid">
          <!-- Dialogue Section -->
          <div class="config-section">
            <h3 class="section-title">Dialogue (对话)</h3>
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
                placeholder="请输入对话接口地址" />
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
                placeholder="请输入对话模型标识" />
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
                placeholder="请输入 0 到 1" />
              <span class="field-help">
                控制回答稳定性与发散度。值越低越稳，越高越灵活。
              </span>
            </label>
          </div>

          <!-- Embedding Section -->
          <div class="config-section">
            <h3 class="section-title">Embedding (嵌入)</h3>
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
                placeholder="请输入嵌入接口地址" />
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
                placeholder="请输入嵌入模型标识" />
              <span class="field-help">
                文档切片与问题向量化所使用的嵌入模型。
              </span>
            </label>
          </div>

          <!-- Reranker Section -->
          <div class="config-section">
            <h3 class="section-title">Reranker (重排)</h3>
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
                placeholder="请输入重排接口地址" />
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
                placeholder="请输入重排模型标识" />
              <span class="field-help">
                用于对召回结果再次排序的模型，决定最终送进上下文窗口的片段优先级。
              </span>
            </label>
          </div>
        </div>
      </article>

      <article class="panel-surface form-panel">
        <div
          class="panel-headline"
          style="
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
          "
          @click="toggleAdvanced">
          <span>{{ isDesktop ? '运行维护' : '公开高级设置' }}</span>
          <DownOutlined
            :class="['advanced-arrow', advancedExpanded ? 'expanded' : '']" />
        </div>
        <div v-if="advancedExpanded" class="ops-stack">
          <p class="panel-copy">
            {{
              isDesktop
                ? '默认情况下只展示常用能力配置。目录、跨域和请求分类等低频参数放在高级设置里，避免干扰日常使用。'
                : '这些参数会保存在当前浏览器，并自动附带到聊天、知识库和来源详情请求中。'
            }}
          </p>

          <div
            class="advanced-grid"
            style="display: flex; flex-direction: column; gap: 16px">
            <section class="advanced-group config-section">
              <div class="advanced-group-head">
                <h3
                  class="section-title"
                  style="
                    margin-bottom: 4px;
                    padding-bottom: 4px;
                    border-bottom: none;
                  ">
                  {{ requestMetadataGroup.title }}
                </h3>
                <div
                  class="advanced-group-copy field-help"
                  style="margin-bottom: 8px">
                  {{ requestMetadataGroup.description }}
                </div>
              </div>
              <div class="field-grid multi-column-grid">
                <label class="field-block">
                  <span class="field-label">请求来源地址</span>
                  <input
                    v-model="form.OPENROUTER_SITE_URL"
                    class="field-input"
                    type="text"
                    placeholder="https://localhost.invalid" />
                  <span class="field-help">
                    当上游网关需要识别请求来源站点时使用。多数场景保持默认即可。
                  </span>
                </label>

                <label class="field-block">
                  <span class="field-label">应用名称</span>
                  <input
                    v-model="form.OPENROUTER_APP_TITLE"
                    class="field-input"
                    type="text"
                    placeholder="RAG.Agent Desktop" />
                  <span class="field-help">
                    当上游网关需要记录请求来自哪个客户端时使用。
                  </span>
                </label>

                <label class="field-block field-span-2">
                  <span class="field-label">请求分类标签</span>
                  <input
                    v-model="form.OPENROUTER_CATEGORIES"
                    class="field-input"
                    type="text"
                    placeholder="general-chat" />
                  <span class="field-help">
                    请求附带的业务标签，用于统计、路由或审计；名称保持通用，不绑定具体供应商。
                  </span>
                </label>
              </div>
            </section>

            <section class="advanced-group config-section">
              <div class="advanced-group-head">
                <h3
                  class="section-title"
                  style="
                    margin-bottom: 4px;
                    padding-bottom: 4px;
                    border-bottom: none;
                  ">
                  {{ embeddingStrategyGroup.title }}
                </h3>
                <div
                  class="advanced-group-copy field-help"
                  style="margin-bottom: 8px">
                  {{ embeddingStrategyGroup.description }}
                </div>
              </div>
              <div class="field-grid multi-column-grid">
                <label class="field-block">
                  <span class="field-label">Embedding Provider</span>
                  <input
                    v-model="form.EMBEDDING_PROVIDER"
                    class="field-input"
                    type="text"
                    placeholder="openai" />
                  <span class="field-help">
                    LiteLLM 调用 embedding 时使用的 provider 标识。OpenAI
                    兼容接口通常填 openai。
                  </span>
                </label>

                <label class="field-block">
                  <span class="field-label">Embedding 最大输入 Token</span>
                  <input
                    v-model.number="form.EMBEDDING_MAX_INPUT_TOKENS"
                    class="field-input"
                    type="number"
                    min="1"
                    step="1"
                    placeholder="512" />
                  <span class="field-help">
                    单段文本允许进入嵌入接口的最大 token
                    数，超过后会自动继续切分。
                  </span>
                </label>

                <label class="field-block">
                  <span class="field-label">Embedding 目标分块 Token</span>
                  <input
                    v-model.number="form.EMBEDDING_TARGET_CHUNK_TOKENS"
                    class="field-input"
                    type="number"
                    min="1"
                    step="1"
                    placeholder="384" />
                  <span class="field-help">
                    二次切分时的目标大小。建议小于最大输入 token，上调会减少
                    chunk 数。
                  </span>
                </label>

                <label class="field-block">
                  <span class="field-label">Embedding 重叠 Token</span>
                  <input
                    v-model.number="form.EMBEDDING_CHUNK_OVERLAP_TOKENS"
                    class="field-input"
                    type="number"
                    min="0"
                    step="1"
                    placeholder="48" />
                  <span class="field-help">
                    相邻分块之间保留的上下文 token
                    数，用于降低切分边界带来的信息断裂。
                  </span>
                </label>

                <label class="field-block">
                  <span class="field-label">Embedding Tokenizer Model</span>
                  <input
                    v-model="form.EMBEDDING_TOKENIZER_MODEL"
                    class="field-input"
                    type="text"
                    placeholder="留空时跟随 EMBEDDING_MODEL" />
                  <span class="field-help">
                    用于 token 计数的模型标识；留空时默认跟随当前 embedding
                    model。
                  </span>
                </label>

                <label class="field-block">
                  <span class="field-label">Embedding Tokenizer Encoding</span>
                  <input
                    v-model="form.EMBEDDING_TOKENIZER_ENCODING"
                    class="field-input"
                    type="text"
                    placeholder="cl100k_base" />
                  <span class="field-help">
                    tokenizer model 无法直接识别时使用的编码兜底值。
                  </span>
                </label>
              </div>
            </section>

            <section class="advanced-group config-section">
              <div class="advanced-group-head">
                <h3
                  class="section-title"
                  style="
                    margin-bottom: 4px;
                    padding-bottom: 4px;
                    border-bottom: none;
                  ">
                  {{ retrievalStrategyGroup.title }}
                </h3>
                <div
                  class="advanced-group-copy field-help"
                  style="margin-bottom: 8px">
                  {{ retrievalStrategyGroup.description }}
                </div>
              </div>
              <div class="field-grid multi-column-grid">
                <label class="field-block">
                  <span class="field-label">Reranker Timeout</span>
                  <input
                    v-model.number="form.RERANKER_REQUEST_TIMEOUT"
                    class="field-input"
                    type="number"
                    min="1"
                    step="1"
                    placeholder="20" />
                  <span class="field-help">
                    重排请求超时时间，单位秒，用于控制直连 rerank
                    接口的等待上限。
                  </span>
                </label>

                <label class="field-block">
                  <span class="field-label">召回候选数量</span>
                  <input
                    v-model.number="form.RETRIEVAL_CANDIDATE_LIMIT"
                    class="field-input"
                    type="number"
                    min="1"
                    step="1"
                    placeholder="18" />
                  <span class="field-help">
                    每次检索阶段先召回多少个候选片段。多知识库场景下适当调高有助于减少漏召回。
                  </span>
                </label>

                <label class="field-block">
                  <span class="field-label">最终上下文数量</span>
                  <input
                    v-model.number="form.RETRIEVAL_FINAL_CONTEXT_LIMIT"
                    class="field-input"
                    type="number"
                    min="1"
                    step="1"
                    placeholder="5" />
                  <span class="field-help">
                    重排后最多保留多少个片段进入答案上下文。值越高，引用更充分，但生成成本也会上升。
                  </span>
                </label>

                <label class="field-block">
                  <span class="field-label">引用来源数量</span>
                  <input
                    v-model.number="form.RETRIEVAL_SOURCE_LIMIT"
                    class="field-input"
                    type="number"
                    min="1"
                    step="1"
                    placeholder="5" />
                  <span class="field-help">
                    回答完成后最多展示多少条引用来源。建议与最终上下文数量保持一致或略小。
                  </span>
                </label>

                <label class="field-block">
                  <span class="field-label">问题扩写数量</span>
                  <input
                    v-model.number="form.RETRIEVAL_QUERY_EXPANSION_COUNT"
                    class="field-input"
                    type="number"
                    min="0"
                    step="1"
                    placeholder="3" />
                  <span class="field-help">
                    口语问题会先扩写出多少个更正式的相近问法再做召回。填 0
                    表示关闭扩写。
                  </span>
                </label>
              </div>
            </section>

            <section class="advanced-group config-section">
              <div class="advanced-group-head">
                <h3
                  class="section-title"
                  style="
                    margin-bottom: 4px;
                    padding-bottom: 4px;
                    border-bottom: none;
                  ">
                  {{ storageRuntimeGroup.title }}
                </h3>
                <div
                  class="advanced-group-copy field-help"
                  style="margin-bottom: 8px">
                  {{ storageRuntimeGroup.description }}
                </div>
              </div>
              <div class="field-grid multi-column-grid">
                <label v-if="isDesktop" class="field-block">
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
                    持久化目录，保存向量索引与本地检索数据。只有在迁移或隔离数据时才需要修改。
                  </span>
                </label>

                <label v-if="isDesktop" class="field-block">
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

                <label v-if="isDesktop" class="field-block field-span-2">
                  <span class="field-label">CORS Origins</span>
                  <input
                    v-model="form.CORS_ORIGINS"
                    class="field-input"
                    type="text"
                    placeholder="http://localhost:5173,http://localhost:3000,null" />
                  <span class="field-help">
                    允许访问本地后端的前端来源列表。桌面版通常无需调整，联调其他前端时再修改。
                  </span>
                </label>
              </div>
            </section>
          </div>
        </div>
      </article>
    </section>

    <section class="panel-surface action-panel">
      <div v-if="notice" :class="['notice-strip', `notice-${notice.type}`]">
        {{ notice.text }}
      </div>

      <section class="provider-panel">
        <div class="provider-panel-head">
          <div>
            <div class="panel-headline provider-headline">Provider 检测</div>
            <div class="provider-subtitle">
              {{
                isDesktop
                  ? '检查 Embedding、Reranker 和 Chat 三类上游配置是否可用。'
                  : 'Web 端显示脱敏后的 Provider 检测结果，不返回后端敏感配置明细。'
              }}
            </div>
          </div>
          <button
            type="button"
            class="secondary-action"
            :disabled="loading || saving || providerHealthLoading"
            @click="checkProviderHealth()">
            <ReloadOutlined :class="{ spin: providerHealthLoading }" />
            {{ providerHealthLoading ? '检测中...' : '检测 Provider 连接' }}
          </button>
        </div>

        <div class="provider-grid">
          <article
            v-for="entry in providerEntries"
            :key="entry.key"
            :class="[
              'provider-card',
              getProviderCardClass(entry.item?.status || '')
            ]">
            <div class="provider-card-head">
              <div class="provider-title-wrap">
                <div class="provider-title">{{ entry.title }}</div>
                <div class="provider-model">
                  {{ entry.item?.model || '未检测' }}
                </div>
              </div>
              <div class="provider-state-chip">
                <CheckCircleOutlined v-if="entry.item?.status === 'ok'" />
                <WarningOutlined v-else />
                <span>
                  {{ getProviderStateLabel(entry.item?.status || '') }}
                </span>
              </div>
            </div>
            <div class="provider-message">
              {{ entry.item?.message || '尚未执行检测。' }}
            </div>
            <div v-if="entry.item?.detail" class="provider-detail">
              {{ entry.item.detail }}
            </div>
            <div class="provider-kv-list">
              <div class="provider-kv-item">
                <span class="provider-kv-label">Provider</span>
                <span class="provider-kv-value">
                  {{ formatProviderLabel(entry.item?.provider) }}
                </span>
              </div>
              <div class="provider-kv-item">
                <span class="provider-kv-label">探测方式</span>
                <span class="provider-kv-value">
                  {{ formatProbeMode(entry.item?.probe_mode) }}
                </span>
              </div>
              <div class="provider-kv-item">
                <span class="provider-kv-label">Token</span>
                <span class="provider-kv-value">
                  {{ formatTokenUsage(entry.item?.token_usage) }}
                </span>
              </div>
            </div>
            <div class="provider-meta">{{ entry.item?.base_url || '—' }}</div>
          </article>
        </div>
      </section>

      <div class="action-row">
        <button
          type="button"
          class="primary-action"
          :disabled="loading || saving"
          @click="saveConfig">
          {{
            isDesktop
              ? saving
                ? '正在保存并重启服务...'
                : '保存配置并重启服务'
              : saving
                ? '正在保存浏览器设置...'
                : '保存浏览器设置'
          }}
        </button>
        <button
          v-if="isDesktop"
          type="button"
          class="secondary-action"
          :disabled="loading || saving"
          @click="restartBackend">
          <ReloadOutlined />
          手动重启服务
        </button>
        <button
          v-if="isDesktop"
          type="button"
          class="secondary-action"
          :disabled="loading || saving"
          @click="openDataDirectory">
          <FolderOpenOutlined />
          打开数据目录
        </button>
        <button
          v-if="!isDesktop"
          type="button"
          class="secondary-action"
          :disabled="saving"
          @click="resetWebConfig">
          恢复默认设置
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.settings-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 16px;
  padding-bottom: 18px;
}

.panel-surface {
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(24, 24, 27, 0.06);
  box-shadow: 0 20px 50px rgba(24, 24, 27, 0.04);
  border-radius: 22px;
  padding: 22px;
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
  font-size: 30px;
  line-height: 1.1;
  letter-spacing: -0.04em;
  color: #18181b;
}

.hero-copy {
  margin: 10px 0 0;
  max-width: 680px;
  line-height: 1.65;
  color: #71717a;
  font-size: 13px;
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
  padding: 8px 12px;
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

.status-browser {
  background: var(--color-success-soft);
  color: var(--color-success-strong);
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
  font-size: 18px;
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
  gap: 12px;
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
  gap: 16px;
}

.form-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.multi-column-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  align-items: start;
}

.config-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: linear-gradient(180deg, #fcfcfd 0%, #f7f7f8 100%);
  padding: 18px;
  border-radius: 18px;
  border: 1px solid rgba(24, 24, 27, 0.07);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.85);
}

.section-title {
  font-size: 14px;
  font-weight: 700;
  color: #18181b;
  margin-bottom: 4px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(24, 24, 27, 0.06);
}

.advanced-group {
  gap: 16px;
}

.advanced-group-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.advanced-group-copy {
  max-width: 760px;
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
  gap: 6px;
}

.field-label {
  font-size: 13px;
  font-weight: 600;
  color: #3f3f46;
}

.field-help {
  font-size: 12px;
  line-height: 1.55;
  color: #71717a;
}

.field-input {
  width: 100%;
  min-height: 40px;
  border-radius: 12px;
  border: 1px solid rgba(24, 24, 27, 0.12);
  background: #fcfcfd;
  padding: 10px 12px;
  font-size: 14px;
  color: #18181b;
  outline: none;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}

.field-input:focus {
  border-color: var(--color-success-border);
  box-shadow: 0 0 0 4px var(--color-success-soft);
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
  border-radius: 12px;
  padding: 0 16px;
  min-height: 40px;
  background: #f4f4f5;
  color: #3f3f46;
  font-weight: 600;
}

.primary-action {
  min-height: 42px;
  border-radius: 12px;
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

.provider-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.provider-panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.provider-headline {
  font-size: 18px;
}

.provider-subtitle {
  margin-top: 6px;
  color: #71717a;
  font-size: 13px;
}

.provider-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.provider-card {
  border-radius: 18px;
  border: 1px solid rgba(24, 24, 27, 0.08);
  background: linear-gradient(180deg, #fcfcfd 0%, #f5f5f5 100%);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.provider-card-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}

.provider-title {
  color: #18181b;
  font-size: 15px;
  font-weight: 700;
}

.provider-model,
.provider-meta,
.provider-message {
  color: #71717a;
  font-size: 12px;
  line-height: 1.6;
  word-break: break-all;
}

.provider-detail {
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(24, 24, 27, 0.04);
  border: 1px solid rgba(24, 24, 27, 0.06);
  color: #52525b;
  font-size: 12px;
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
}

.provider-kv-list {
  display: grid;
  gap: 8px;
}

.provider-kv-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  padding-top: 8px;
  border-top: 1px solid rgba(24, 24, 27, 0.06);
}

.provider-kv-label {
  color: #71717a;
  font-size: 12px;
}

.provider-kv-value {
  color: #27272a;
  font-size: 12px;
  font-weight: 600;
  text-align: right;
}

.provider-state-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.provider-card-ok .provider-state-chip {
  background: rgba(37, 99, 65, 0.12);
  color: #1f6b42;
}

.provider-card-missing .provider-state-chip,
.provider-card-warning .provider-state-chip {
  background: rgba(180, 125, 29, 0.12);
  color: #9f670f;
}

.provider-card-error .provider-state-chip {
  background: rgba(177, 55, 42, 0.12);
  color: #9e3328;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.notice-strip {
  border-radius: 14px;
  padding: 12px 14px;
  font-size: 13px;
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

  .multi-column-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .hero-status {
    align-items: flex-start;
    min-width: auto;
  }
}

@media (max-width: 768px) {
  .panel-surface {
    padding: 16px;
    border-radius: 18px;
  }

  .hero-title {
    font-size: 24px;
  }

  .field-grid,
  .path-input-wrap {
    grid-template-columns: 1fr;
  }

  .multi-column-grid {
    grid-template-columns: 1fr;
  }

  .provider-panel-head,
  .provider-grid {
    display: grid;
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
