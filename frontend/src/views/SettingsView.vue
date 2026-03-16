<script setup lang="ts">
defineOptions({
  name: 'SettingsView'
});

import { computed, onMounted, reactive, ref, watch } from 'vue';
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
import { OButton, OCard, OInput, useOToast } from '@/orange-ui';
import { cn } from '@/utils/cn';

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
const oToast = useOToast();

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

watch(notice, (nextNotice) => {
  if (!nextNotice) return;
  if (nextNotice.type === 'error') {
    oToast.error(nextNotice.text);
    return;
  }

  oToast.success(nextNotice.text);
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

function getStatusChipClass(
  status: 'unknown' | 'online' | 'offline' | 'restarting'
) {
  if (status === 'online') {
    return 'bg-[rgba(37,99,65,0.12)] text-[#1f6b42]';
  }

  if (status === 'offline') {
    return 'bg-[rgba(177,55,42,0.12)] text-[#9e3328]';
  }

  return 'bg-[rgba(180,125,29,0.12)] text-[#9f670f]';
}

function getProviderCardTone(
  status: string
): 'muted' | 'success' | 'warning' | 'danger' {
  if (status === 'ok') return 'success';
  if (status === 'auth_error') return 'danger';
  if (status === 'missing_config') return 'warning';
  return 'muted';
}

function getProviderStateChipClass(status: string) {
  if (status === 'ok') {
    return 'bg-[rgba(37,99,65,0.12)] text-[#1f6b42]';
  }

  if (
    status === 'missing_config' ||
    status === 'timeout' ||
    status === 'network_error' ||
    status === 'upstream_error'
  ) {
    return 'bg-[rgba(180,125,29,0.12)] text-[#9f670f]';
  }

  if (status === 'auth_error') {
    return 'bg-[rgba(177,55,42,0.12)] text-[#9e3328]';
  }

  return 'bg-[rgba(180,125,29,0.12)] text-[#9f670f]';
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
  <div class="flex flex-col gap-4 pt-4 pb-4.5">
    <OCard
      padding="lg"
      html-class="flex items-start justify-between gap-6 max-[960px]:grid max-[960px]:grid-cols-1">
      <div>
        <div
          class="mb-3 text-xs font-bold uppercase tracking-[0.08em] text-zinc-500">
          {{ isDesktop ? 'Desktop Runtime' : 'Web Runtime' }}
        </div>
        <h1
          class="m-0 text-[30px] leading-[1.1] font-bold tracking-[-0.04em] text-zinc-900 max-[768px]:text-2xl">
          {{ isDesktop ? '本地服务配置' : '公开高级设置' }}
        </h1>
        <p class="mt-2.5 max-w-170 text-[13px] leading-[1.65] text-zinc-500">
          {{
            isDesktop
              ? '桌面端可配置完整运行参数；敏感 API 凭据仍保存在本地环境。'
              : 'Web 端对用户开放公开高级设置，配置保存在当前浏览器，并会随请求发送给后端；基础 API 配置不会在前端暴露。'
          }}
        </p>
      </div>
      <div
        class="flex min-w-60 flex-col items-end gap-2.5 max-[960px]:min-w-0 max-[960px]:items-start">
        <div
          :class="
            cn(
              'inline-flex items-center gap-2 rounded-full px-3 py-2 text-[13px] font-semibold',
              getStatusChipClass(health)
            )
          ">
          <CloudServerOutlined />
          <span>{{ healthText }}</span>
        </div>
        <div class="text-[13px] text-zinc-500">API 地址：{{ apiBase }}</div>
      </div>
    </OCard>

    <OCard
      v-if="!isDesktop"
      tone="warning"
      html-class="flex items-center gap-4">
      <WarningOutlined class="text-[26px] text-[#9e3328]" />
      <div>
        <h2>当前为 Web 公开设置模式</h2>
        <p>
          当前页面对 Web 用户开放，但仅显示不会泄露凭据的高级设置。基础 API
          Key、Base URL 与 Model 仍由服务端或桌面端托管。
        </p>
      </div>
    </OCard>

    <section
      class="grid grid-cols-[minmax(0,1fr)] gap-4 max-[960px]:grid max-[960px]:grid-cols-1">
      <OCard v-if="isDesktop" padding="lg" html-class="flex flex-col gap-3.5">
        <div class="text-lg font-bold tracking-[-0.02em] text-zinc-900">
          能力配置
        </div>
        <div
          class="grid grid-cols-3 items-start gap-4 max-[960px]:grid-cols-2 max-[768px]:grid-cols-1">
          <!-- Dialogue Section -->
          <div
            class="flex flex-col gap-3 rounded-[18px] border border-black/7 bg-linear-to-b from-[#fcfcfd] to-[#f7f7f8] p-4.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
            <h3
              class="mb-1 border-b border-black/6 pb-2.5 text-sm font-bold text-zinc-900">
              Dialogue (对话)
            </h3>
            <label class="flex flex-col gap-1.5">
              <span class="text-[13px] font-semibold text-zinc-700">
                对话 API Key
              </span>
              <OInput
                v-model="form.CHAT_API_KEY"
                type="password"
                placeholder="用于对话能力调用" />
              <span class="text-xs leading-[1.55] text-zinc-500">
                对话模型请求使用的密钥。具体由你接入的 LiteLLM
                后端或代理策略决定。
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <span class="text-[13px] font-semibold text-zinc-700">
                对话 EndPoint
              </span>
              <OInput
                v-model="form.CHAT_BASE_URL"
                type="text"
                placeholder="请输入对话接口地址" />
              <span class="text-xs leading-[1.55] text-zinc-500">
                对话请求发送到的接口地址。由于底层走
                LiteLLM，这里不限定具体服务商。
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <span class="text-[13px] font-semibold text-zinc-700">
                对话 Model
              </span>
              <OInput
                v-model="form.CHAT_MODEL"
                type="text"
                placeholder="请输入对话模型标识" />
              <span class="text-xs leading-[1.55] text-zinc-500">
                对话能力使用的模型标识，格式由你的 LiteLLM 路由规则决定。
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <span class="text-[13px] font-semibold text-zinc-700">温度</span>
              <OInput
                v-model="form.CHAT_TEMPERATURE"
                type="number"
                min="0"
                max="1"
                step="0.1"
                placeholder="请输入 0 到 1" />
              <span class="text-xs leading-[1.55] text-zinc-500">
                控制回答稳定性与发散度。值越低越稳，越高越灵活。
              </span>
            </label>
          </div>

          <!-- Embedding Section -->
          <div
            class="flex flex-col gap-3 rounded-[18px] border border-black/7 bg-linear-to-b from-[#fcfcfd] to-[#f7f7f8] p-4.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
            <h3
              class="mb-1 border-b border-black/6 pb-2.5 text-sm font-bold text-zinc-900">
              Embedding (嵌入)
            </h3>
            <label class="flex flex-col gap-1.5">
              <span class="text-[13px] font-semibold text-zinc-700">
                嵌入 API Key
              </span>
              <OInput
                v-model="form.EMBEDDING_API_KEY"
                type="password"
                placeholder="用于嵌入能力调用" />
              <span class="text-xs leading-[1.55] text-zinc-500">
                文档分块和问题向量化所使用的密钥。可以与对话、重排分别使用不同提供商。
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <span class="text-[13px] font-semibold text-zinc-700">
                嵌入 EndPoint
              </span>
              <OInput
                v-model="form.EMBEDDING_BASE_URL"
                type="text"
                placeholder="请输入嵌入接口地址" />
              <span class="text-xs leading-[1.55] text-zinc-500">
                嵌入请求发送到的接口地址。可独立于重排和对话配置。
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <span class="text-[13px] font-semibold text-zinc-700">
                嵌入 Model
              </span>
              <OInput
                v-model="form.EMBEDDING_MODEL"
                type="text"
                placeholder="请输入嵌入模型标识" />
              <span class="text-xs leading-[1.55] text-zinc-500">
                文档切片与问题向量化所使用的嵌入模型。
              </span>
            </label>
          </div>

          <!-- Reranker Section -->
          <div
            class="flex flex-col gap-3 rounded-[18px] border border-black/7 bg-linear-to-b from-[#fcfcfd] to-[#f7f7f8] p-4.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
            <h3
              class="mb-1 border-b border-black/6 pb-2.5 text-sm font-bold text-zinc-900">
              Reranker (重排)
            </h3>
            <label class="flex flex-col gap-1.5">
              <span class="text-[13px] font-semibold text-zinc-700">
                重排 API Key
              </span>
              <OInput
                v-model="form.RERANKER_API_KEY"
                type="password"
                placeholder="用于重排能力调用" />
              <span class="text-xs leading-[1.55] text-zinc-500">
                候选片段二次排序所使用的密钥。需要与嵌入或对话分供应商时单独配置这里。
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <span class="text-[13px] font-semibold text-zinc-700">
                重排 EndPoint
              </span>
              <OInput
                v-model="form.RERANKER_BASE_URL"
                type="text"
                placeholder="请输入重排接口地址" />
              <span class="text-xs leading-[1.55] text-zinc-500">
                重排请求发送到的接口地址。可与嵌入完全不同。
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <span class="text-[13px] font-semibold text-zinc-700">
                重排 Model
              </span>
              <OInput
                v-model="form.RERANKER_MODEL"
                type="text"
                placeholder="请输入重排模型标识" />
              <span class="text-xs leading-[1.55] text-zinc-500">
                用于对召回结果再次排序的模型，决定最终送进上下文窗口的片段优先级。
              </span>
            </label>
          </div>
        </div>
      </OCard>

      <OCard padding="lg" html-class="flex flex-col gap-3.5">
        <div
          class="flex cursor-pointer items-center justify-between text-lg font-bold tracking-[-0.02em] text-zinc-900"
          @click="toggleAdvanced">
          <span>{{ isDesktop ? '运行维护' : '公开高级设置' }}</span>
          <DownOutlined
            :class="[
              'transition-transform duration-200',
              advancedExpanded ? 'rotate-180' : ''
            ]" />
        </div>
        <div v-if="advancedExpanded" class="flex flex-col gap-3">
          <p class="text-zinc-500 leading-[1.7]">
            {{
              isDesktop
                ? '默认情况下只展示常用能力配置。目录、跨域和请求分类等低频参数放在高级设置里，避免干扰日常使用。'
                : '这些参数会保存在当前浏览器，并自动附带到聊天、知识库和来源详情请求中。'
            }}
          </p>

          <div class="flex flex-col gap-4 pt-1.5">
            <section
              class="flex flex-col gap-4 rounded-[18px] border border-black/7 bg-linear-to-b from-[#fcfcfd] to-[#f7f7f8] p-4.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
              <div class="flex flex-col gap-1">
                <h3
                  class="mb-1 border-b-0 pb-1 text-sm font-bold text-zinc-900"
                  style="border-bottom: none">
                  {{ requestMetadataGroup.title }}
                </h3>
                <div
                  class="mb-2 max-w-190 text-xs leading-[1.55] text-zinc-500">
                  {{ requestMetadataGroup.description }}
                </div>
              </div>
              <div
                class="grid grid-cols-3 items-start gap-4 max-[960px]:grid-cols-2 max-[768px]:grid-cols-1">
                <label class="flex flex-col gap-1.5">
                  <span class="text-[13px] font-semibold text-zinc-700">
                    请求来源地址
                  </span>
                  <OInput
                    v-model="form.OPENROUTER_SITE_URL"
                    type="text"
                    placeholder="https://localhost.invalid" />
                  <span class="text-xs leading-[1.55] text-zinc-500">
                    当上游网关需要识别请求来源站点时使用。多数场景保持默认即可。
                  </span>
                </label>

                <label class="flex flex-col gap-1.5">
                  <span class="text-[13px] font-semibold text-zinc-700">
                    应用名称
                  </span>
                  <OInput
                    v-model="form.OPENROUTER_APP_TITLE"
                    type="text"
                    placeholder="RAG.Agent Desktop" />
                  <span class="text-xs leading-[1.55] text-zinc-500">
                    当上游网关需要记录请求来自哪个客户端时使用。
                  </span>
                </label>

                <label
                  class="col-span-2 flex flex-col gap-1.5 max-[768px]:col-span-1">
                  <span class="text-[13px] font-semibold text-zinc-700">
                    请求分类标签
                  </span>
                  <OInput
                    v-model="form.OPENROUTER_CATEGORIES"
                    type="text"
                    placeholder="general-chat" />
                  <span class="text-xs leading-[1.55] text-zinc-500">
                    请求附带的业务标签，用于统计、路由或审计；名称保持通用，不绑定具体供应商。
                  </span>
                </label>
              </div>
            </section>

            <section
              class="flex flex-col gap-4 rounded-[18px] border border-black/7 bg-linear-to-b from-[#fcfcfd] to-[#f7f7f8] p-4.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
              <div class="flex flex-col gap-1">
                <h3
                  class="mb-1 border-b-0 pb-1 text-sm font-bold text-zinc-900"
                  style="border-bottom: none">
                  {{ embeddingStrategyGroup.title }}
                </h3>
                <div
                  class="mb-2 max-w-190 text-xs leading-[1.55] text-zinc-500">
                  {{ embeddingStrategyGroup.description }}
                </div>
              </div>
              <div
                class="grid grid-cols-3 items-start gap-4 max-[960px]:grid-cols-2 max-[768px]:grid-cols-1">
                <label class="flex flex-col gap-1.5">
                  <span class="text-[13px] font-semibold text-zinc-700">
                    Embedding Provider
                  </span>
                  <OInput
                    v-model="form.EMBEDDING_PROVIDER"
                    type="text"
                    placeholder="openai" />
                  <span class="text-xs leading-[1.55] text-zinc-500">
                    LiteLLM 调用 embedding 时使用的 provider 标识。OpenAI
                    兼容接口通常填 openai。
                  </span>
                </label>

                <label class="flex flex-col gap-1.5">
                  <span class="text-[13px] font-semibold text-zinc-700">
                    Embedding 最大输入 Token
                  </span>
                  <OInput
                    v-model="form.EMBEDDING_MAX_INPUT_TOKENS"
                    type="number"
                    min="1"
                    step="1"
                    placeholder="512" />
                  <span class="text-xs leading-[1.55] text-zinc-500">
                    单段文本允许进入嵌入接口的最大 token
                    数，超过后会自动继续切分。
                  </span>
                </label>

                <label class="flex flex-col gap-1.5">
                  <span class="text-[13px] font-semibold text-zinc-700">
                    Embedding 目标分块 Token
                  </span>
                  <OInput
                    v-model="form.EMBEDDING_TARGET_CHUNK_TOKENS"
                    type="number"
                    min="1"
                    step="1"
                    placeholder="384" />
                  <span class="text-xs leading-[1.55] text-zinc-500">
                    二次切分时的目标大小。建议小于最大输入 token，上调会减少
                    chunk 数。
                  </span>
                </label>

                <label class="flex flex-col gap-1.5">
                  <span class="text-[13px] font-semibold text-zinc-700">
                    Embedding 重叠 Token
                  </span>
                  <OInput
                    v-model="form.EMBEDDING_CHUNK_OVERLAP_TOKENS"
                    type="number"
                    min="0"
                    step="1"
                    placeholder="48" />
                  <span class="text-xs leading-[1.55] text-zinc-500">
                    相邻分块之间保留的上下文 token
                    数，用于降低切分边界带来的信息断裂。
                  </span>
                </label>

                <label class="flex flex-col gap-1.5">
                  <span class="text-[13px] font-semibold text-zinc-700">
                    Embedding Tokenizer Model
                  </span>
                  <OInput
                    v-model="form.EMBEDDING_TOKENIZER_MODEL"
                    type="text"
                    placeholder="留空时跟随 EMBEDDING_MODEL" />
                  <span class="text-xs leading-[1.55] text-zinc-500">
                    用于 token 计数的模型标识；留空时默认跟随当前 embedding
                    model。
                  </span>
                </label>

                <label class="flex flex-col gap-1.5">
                  <span class="text-[13px] font-semibold text-zinc-700">
                    Embedding Tokenizer Encoding
                  </span>
                  <OInput
                    v-model="form.EMBEDDING_TOKENIZER_ENCODING"
                    type="text"
                    placeholder="cl100k_base" />
                  <span class="text-xs leading-[1.55] text-zinc-500">
                    tokenizer model 无法直接识别时使用的编码兜底值。
                  </span>
                </label>
              </div>
            </section>

            <section
              class="flex flex-col gap-4 rounded-[18px] border border-black/7 bg-linear-to-b from-[#fcfcfd] to-[#f7f7f8] p-4.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
              <div class="flex flex-col gap-1">
                <h3
                  class="mb-1 border-b-0 pb-1 text-sm font-bold text-zinc-900"
                  style="border-bottom: none">
                  {{ retrievalStrategyGroup.title }}
                </h3>
                <div
                  class="mb-2 max-w-190 text-xs leading-[1.55] text-zinc-500">
                  {{ retrievalStrategyGroup.description }}
                </div>
              </div>
              <div
                class="grid grid-cols-3 items-start gap-4 max-[960px]:grid-cols-2 max-[768px]:grid-cols-1">
                <label class="flex flex-col gap-1.5">
                  <span class="text-[13px] font-semibold text-zinc-700">
                    Reranker Timeout
                  </span>
                  <OInput
                    v-model="form.RERANKER_REQUEST_TIMEOUT"
                    type="number"
                    min="1"
                    step="1"
                    placeholder="20" />
                  <span class="text-xs leading-[1.55] text-zinc-500">
                    重排请求超时时间，单位秒，用于控制直连 rerank
                    接口的等待上限。
                  </span>
                </label>

                <label class="flex flex-col gap-1.5">
                  <span class="text-[13px] font-semibold text-zinc-700">
                    召回候选数量
                  </span>
                  <OInput
                    v-model="form.RETRIEVAL_CANDIDATE_LIMIT"
                    type="number"
                    min="1"
                    step="1"
                    placeholder="18" />
                  <span class="text-xs leading-[1.55] text-zinc-500">
                    每次检索阶段先召回多少个候选片段。多知识库场景下适当调高有助于减少漏召回。
                  </span>
                </label>

                <label class="flex flex-col gap-1.5">
                  <span class="text-[13px] font-semibold text-zinc-700">
                    最终上下文数量
                  </span>
                  <OInput
                    v-model="form.RETRIEVAL_FINAL_CONTEXT_LIMIT"
                    type="number"
                    min="1"
                    step="1"
                    placeholder="5" />
                  <span class="text-xs leading-[1.55] text-zinc-500">
                    重排后最多保留多少个片段进入答案上下文。值越高，引用更充分，但生成成本也会上升。
                  </span>
                </label>

                <label class="flex flex-col gap-1.5">
                  <span class="text-[13px] font-semibold text-zinc-700">
                    引用来源数量
                  </span>
                  <OInput
                    v-model="form.RETRIEVAL_SOURCE_LIMIT"
                    type="number"
                    min="1"
                    step="1"
                    placeholder="5" />
                  <span class="text-xs leading-[1.55] text-zinc-500">
                    回答完成后最多展示多少条引用来源。建议与最终上下文数量保持一致或略小。
                  </span>
                </label>

                <label class="flex flex-col gap-1.5">
                  <span class="text-[13px] font-semibold text-zinc-700">
                    问题扩写数量
                  </span>
                  <OInput
                    v-model="form.RETRIEVAL_QUERY_EXPANSION_COUNT"
                    type="number"
                    min="0"
                    step="1"
                    placeholder="3" />
                  <span class="text-xs leading-[1.55] text-zinc-500">
                    口语问题会先扩写出多少个更正式的相近问法再做召回。填 0
                    表示关闭扩写。
                  </span>
                </label>
              </div>
            </section>

            <section
              class="flex flex-col gap-4 rounded-[18px] border border-black/7 bg-linear-to-b from-[#fcfcfd] to-[#f7f7f8] p-4.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
              <div class="flex flex-col gap-1">
                <h3
                  class="mb-1 border-b-0 pb-1 text-sm font-bold text-zinc-900"
                  style="border-bottom: none">
                  {{ storageRuntimeGroup.title }}
                </h3>
                <div
                  class="mb-2 max-w-190 text-xs leading-[1.55] text-zinc-500">
                  {{ storageRuntimeGroup.description }}
                </div>
              </div>
              <div
                class="grid grid-cols-3 items-start gap-4 max-[960px]:grid-cols-2 max-[768px]:grid-cols-1">
                <label v-if="isDesktop" class="flex flex-col gap-1.5">
                  <span class="text-[13px] font-semibold text-zinc-700">
                    向量库目录
                  </span>
                  <div
                    class="grid grid-cols-[minmax(0,1fr)_auto] gap-2.5 max-[768px]:grid-cols-1">
                    <OInput
                      v-model="form.CHROMA_PERSIST_DIR"
                      type="text"
                      placeholder="例如 ./data/chroma" />
                    <OButton
                      variant="secondary"
                      html-class="shrink-0"
                      @click="pickDirectory('CHROMA_PERSIST_DIR')">
                      <FolderOpenOutlined />
                      选择目录
                    </OButton>
                  </div>
                  <span class="text-xs leading-[1.55] text-zinc-500">
                    Chroma
                    持久化目录，保存向量索引与本地检索数据。只有在迁移或隔离数据时才需要修改。
                  </span>
                </label>

                <label v-if="isDesktop" class="flex flex-col gap-1.5">
                  <span class="text-[13px] font-semibold text-zinc-700">
                    上传文件目录
                  </span>
                  <div
                    class="grid grid-cols-[minmax(0,1fr)_auto] gap-2.5 max-[768px]:grid-cols-1">
                    <OInput
                      v-model="form.UPLOAD_DIR"
                      type="text"
                      placeholder="例如 ./data/uploads" />
                    <OButton
                      variant="secondary"
                      html-class="shrink-0"
                      @click="pickDirectory('UPLOAD_DIR')">
                      <FolderOpenOutlined />
                      选择目录
                    </OButton>
                  </div>
                  <span class="text-xs leading-[1.55] text-zinc-500">
                    原始上传文档的存放目录。修改后适合把资料与应用程序分开管理。
                  </span>
                </label>

                <label
                  v-if="isDesktop"
                  class="col-span-2 flex flex-col gap-1.5 max-[768px]:col-span-1">
                  <span class="text-[13px] font-semibold text-zinc-700">
                    CORS Origins
                  </span>
                  <OInput
                    v-model="form.CORS_ORIGINS"
                    type="text"
                    placeholder="http://localhost:5173,http://localhost:3000,null" />
                  <span class="text-xs leading-[1.55] text-zinc-500">
                    允许访问本地后端的前端来源列表。桌面版通常无需调整，联调其他前端时再修改。
                  </span>
                </label>
              </div>
            </section>
          </div>
        </div>
      </OCard>
    </section>

    <OCard padding="lg" html-class="flex flex-col gap-4">
      <section class="flex flex-col gap-3">
        <div
          class="flex items-start justify-between gap-4 max-[768px]:grid max-[768px]:grid-cols-1">
          <div>
            <div class="text-lg font-bold tracking-[-0.02em] text-zinc-900">
              Provider 检测
            </div>
            <div class="mt-1.5 text-[13px] text-zinc-500">
              {{
                isDesktop
                  ? '检查 Embedding、Reranker 和 Chat 三类上游配置是否可用。'
                  : 'Web 端显示脱敏后的 Provider 检测结果，不返回后端敏感配置明细。'
              }}
            </div>
          </div>
          <OButton
            variant="secondary"
            :disabled="loading || saving || providerHealthLoading"
            :loading="providerHealthLoading"
            @click="checkProviderHealth()">
            {{ providerHealthLoading ? '检测中...' : '检测 Provider 连接' }}
          </OButton>
        </div>

        <div class="grid grid-cols-3 gap-3 max-[768px]:grid-cols-1">
          <OCard
            v-for="entry in providerEntries"
            :key="entry.key"
            padding="sm"
            :tone="getProviderCardTone(entry.item?.status || '')"
            html-class="flex flex-col gap-2.5">
            <div class="flex items-start justify-between gap-2.5">
              <div class="provider-title-wrap">
                <div class="text-[15px] font-bold text-zinc-900">
                  {{ entry.title }}
                </div>
                <div class="break-all text-xs leading-6 text-zinc-500">
                  {{ entry.item?.model || '未检测' }}
                </div>
              </div>
              <div
                :class="
                  cn(
                    'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-xs font-bold whitespace-nowrap',
                    getProviderStateChipClass(entry.item?.status || '')
                  )
                ">
                <CheckCircleOutlined v-if="entry.item?.status === 'ok'" />
                <WarningOutlined v-else />
                <span>
                  {{ getProviderStateLabel(entry.item?.status || '') }}
                </span>
              </div>
            </div>
            <div class="break-all text-xs leading-6 text-zinc-500">
              {{ entry.item?.message || '尚未执行检测。' }}
            </div>
            <div
              v-if="entry.item?.detail"
              class="rounded-[14px] border border-black/6 bg-black/4 px-3 py-2.5 text-xs leading-6 text-zinc-600 wrap-break-word whitespace-pre-wrap">
              {{ entry.item.detail }}
            </div>
            <div class="grid gap-2">
              <div
                class="flex items-start justify-between gap-3 border-t border-black/6 pt-2">
                <span class="text-xs text-zinc-500">Provider</span>
                <span class="text-right text-xs font-semibold text-zinc-800">
                  {{ formatProviderLabel(entry.item?.provider) }}
                </span>
              </div>
              <div
                class="flex items-start justify-between gap-3 border-t border-black/6 pt-2">
                <span class="text-xs text-zinc-500">探测方式</span>
                <span class="text-right text-xs font-semibold text-zinc-800">
                  {{ formatProbeMode(entry.item?.probe_mode) }}
                </span>
              </div>
              <div
                class="flex items-start justify-between gap-3 border-t border-black/6 pt-2">
                <span class="text-xs text-zinc-500">Token</span>
                <span class="text-right text-xs font-semibold text-zinc-800">
                  {{ formatTokenUsage(entry.item?.token_usage) }}
                </span>
              </div>
            </div>
            <div class="break-all text-xs leading-6 text-zinc-500">
              {{ entry.item?.base_url || '—' }}
            </div>
          </OCard>
        </div>
      </section>

      <div class="flex flex-wrap gap-3 max-[768px]:flex-col">
        <OButton
          :disabled="loading || saving"
          :loading="saving"
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
        </OButton>
        <OButton
          v-if="isDesktop"
          variant="secondary"
          :disabled="loading || saving"
          @click="restartBackend">
          <ReloadOutlined />
          手动重启服务
        </OButton>
        <OButton
          v-if="isDesktop"
          variant="secondary"
          :disabled="loading || saving"
          @click="openDataDirectory">
          <FolderOpenOutlined />
          打开数据目录
        </OButton>
        <OButton
          v-if="!isDesktop"
          variant="secondary"
          :disabled="saving"
          @click="resetWebConfig">
          恢复默认设置
        </OButton>
      </div>
    </OCard>
  </div>
</template>
