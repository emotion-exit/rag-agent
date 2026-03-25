<script setup lang="ts">
defineOptions({
  name: 'SettingsView'
});

import { computed, onMounted, reactive, ref, watch } from 'vue';
import {
  CheckCircleOutlined,
  CloudServerOutlined,
  DownOutlined,
  WarningOutlined
} from '@ant-design/icons-vue';
import { getApiBase } from '@/services/runtime';
import {
  createManagedUser,
  fetchManagedUsers,
  resetManagedUserPassword,
  updateManagedUser,
  useAuthState,
  type ManagedAuthUser
} from '@/services/auth';
import {
  buildPublicConfigHeaders,
  cloneDefaultPublicFrontendConfig,
  loadPublicFrontendConfig,
  resetPublicFrontendConfig,
  savePublicFrontendConfig,
  type PublicFrontendConfig
} from '@/services/publicConfig';
import {
  OBadge,
  OButton,
  OCard,
  OFormItem,
  OFormSection,
  OInput,
  OModal,
  OSelect,
  useOToast
} from '@/orange-ui';
import { cn } from '@/utils/cn';

const apiBase = getApiBase();
const authState = useAuthState();
const form = reactive<PublicFrontendConfig>(cloneDefaultPublicFrontendConfig());
const loading = ref(false);
const saving = ref(false);
const health = ref<'unknown' | 'online' | 'offline'>('unknown');
const notice = ref<{ type: 'success' | 'error'; text: string } | null>(null);
const advancedExpanded = ref(true);
const providerHealthLoading = ref(false);
const providerHealth = ref<Record<string, ProviderHealthItem>>({});
const managedUsers = ref<ManagedAuthUser[]>([]);
const managedUsersLoading = ref(false);
const createUserModalVisible = ref(false);
const createUserSubmitting = ref(false);
const resetPasswordModalVisible = ref(false);
const resetPasswordSubmitting = ref(false);
const pendingUserActions = reactive<Record<string, boolean>>({});
const createUserForm = reactive({
  username: '',
  password: '',
  role: 'user' as 'admin' | 'user'
});
const resetPasswordForm = reactive({
  userId: '',
  username: '',
  password: ''
});
const oToast = useOToast();

interface ProviderHealthItem {
  status: string;
  configured: boolean;
  message?: string;
  detail?: string;
  base_url?: string;
  model?: string;
  provider?: string;
  probe_mode?: string;
  token_usage?: string;
}

interface ProviderHealthResponse {
  status: string;
  providers?: Record<string, ProviderHealthItem>;
}

interface EffectRuleItem {
  title: string;
  detail: string;
  tone: 'success' | 'warning' | 'neutral';
}

interface ReflectionTokenPreset {
  label: string;
  value: number;
  detail: string;
}

const effectRuleItems: EffectRuleItem[] = [
  {
    title: '下一次请求立即生效',
    detail:
      '公开高级设置保存在当前浏览器，并会自动附带到下一次聊天、知识库和来源详情请求。',
    tone: 'success'
  },
  {
    title: '不会改写后端基础凭据',
    detail:
      'Web 端只发送公开参数，不暴露也不覆盖服务端托管的 API Key、Base URL 和 Model。',
    tone: 'neutral'
  },
  {
    title: '仅保留 Web 所需配置',
    detail: '当前分支已精简为纯 Web 形态，设置页只保留浏览器侧公开能力。',
    tone: 'warning'
  }
];

const healthText = computed(() => {
  if (health.value === 'online') return '后端服务运行中';
  if (health.value === 'offline') return '后端服务不可用';
  return '等待检测服务状态';
});

const isAdminMode = computed(() => authState.session?.user.role === 'admin');
const currentUserId = computed(() =>
  String(authState.session?.user.user_id || '')
);

const userRoleOptions = [
  { label: '普通用户', value: 'user' },
  { label: '管理员', value: 'admin' }
];

const reflectionTokenPresets: ReflectionTokenPreset[] = [
  {
    label: '关闭拦截',
    value: 0,
    detail: '直接放行答案，适合总被反思挡回的弱模型。'
  },
  {
    label: '保守校验',
    value: 128,
    detail: '保留基础 reflection 判定，减少模型负担。'
  },
  {
    label: '默认推荐',
    value: 256,
    detail: '适合大多数通用模型，兼顾稳定性和拦截精度。'
  },
  {
    label: '强校验',
    value: 512,
    detail: '给高能力模型更多反思空间，但输出负担更高。'
  }
];

const managedUserSummary = computed(() => {
  const items = managedUsers.value;
  return {
    total: items.length,
    active: items.filter((item) => item.is_active).length,
    admins: items.filter((item) => item.role === 'admin').length
  };
});

const providerEntries = computed(() => [
  {
    key: 'embedding',
    title: 'Embedding',
    item: providerHealth.value.embedding
  },
  { key: 'reranker', title: 'Reranker', item: providerHealth.value.reranker },
  { key: 'chat', title: 'Chat', item: providerHealth.value.chat }
]);

watch(notice, (nextNotice) => {
  if (!nextNotice) return;
  if (nextNotice.type === 'error') {
    oToast.error(nextNotice.text);
    return;
  }

  oToast.success(nextNotice.text);
});

function getEffectRuleToneClass(tone: EffectRuleItem['tone']) {
  if (tone === 'success') {
    return 'border-[rgba(37,99,65,0.18)] bg-[rgba(37,99,65,0.08)] text-[#1f6b42]';
  }

  if (tone === 'warning') {
    return 'border-[rgba(180,125,29,0.22)] bg-[rgba(180,125,29,0.1)] text-[#9f670f]';
  }

  return 'border-black/8 bg-black/3 text-zinc-700';
}

function getStatusVariant(
  status: 'unknown' | 'online' | 'offline'
): 'success' | 'danger' | 'warning' {
  if (status === 'online') return 'success';
  if (status === 'offline') return 'danger';
  return 'warning';
}

function getProviderStateLabel(status: string) {
  if (status === 'ok') return '连接正常';
  if (status === 'missing_config') return '缺少配置';
  if (status === 'auth_error') return '鉴权失败';
  if (status === 'timeout') return '请求超时';
  if (status === 'network_error') return '网络异常';
  if (status === 'upstream_error') return '上游异常';
  return '待检测';
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

function isReflectionPresetActive(value: number) {
  return Number(form.REFLECTION_TOKENS) === value;
}

function applyReflectionPreset(value: number) {
  form.REFLECTION_TOKENS = value;
}

function formatUserRole(role: ManagedAuthUser['role']) {
  return role === 'admin' ? '管理员' : '普通用户';
}

function formatUserStatus(isActive: boolean) {
  return isActive ? '启用中' : '已停用';
}

function formatDateTime(value: string) {
  if (!value) return '—';

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString('zh-CN', { hour12: false });
}

function setPendingUserAction(userId: string, pending: boolean) {
  const normalizedUserId = String(userId || '');
  if (!normalizedUserId) return;

  if (pending) {
    pendingUserActions[normalizedUserId] = true;
    return;
  }

  delete pendingUserActions[normalizedUserId];
}

function isPendingUserAction(userId: string) {
  return Boolean(pendingUserActions[String(userId || '')]);
}

function upsertManagedUser(nextUser: ManagedAuthUser) {
  const nextItems = [...managedUsers.value];
  const targetIndex = nextItems.findIndex(
    (item) => item.user_id === nextUser.user_id
  );
  if (targetIndex >= 0) {
    nextItems.splice(targetIndex, 1, nextUser);
  } else {
    nextItems.push(nextUser);
  }

  managedUsers.value = nextItems.sort((left, right) => {
    if (left.role !== right.role) {
      return left.role === 'admin' ? -1 : 1;
    }
    return left.created_at.localeCompare(right.created_at);
  });
}

async function loadManagedUserList(options?: { silent?: boolean }) {
  if (!isAdminMode.value) return;

  managedUsersLoading.value = true;
  try {
    managedUsers.value = await fetchManagedUsers();
  } catch (error) {
    if (!options?.silent) {
      oToast.error(
        error instanceof Error ? error.message : '读取用户列表失败。'
      );
    }
  } finally {
    managedUsersLoading.value = false;
  }
}

function openCreateUserModal() {
  createUserForm.username = '';
  createUserForm.password = '';
  createUserForm.role = 'user';
  createUserModalVisible.value = true;
}

function closeCreateUserModal() {
  if (createUserSubmitting.value) return;
  createUserModalVisible.value = false;
}

async function submitCreateUser() {
  if (createUserSubmitting.value) return;

  createUserSubmitting.value = true;
  try {
    const createdUser = await createManagedUser({
      username: createUserForm.username,
      password: createUserForm.password,
      role: createUserForm.role
    });
    upsertManagedUser(createdUser);
    createUserModalVisible.value = false;
    oToast.success('用户创建成功。');
  } catch (error) {
    oToast.error(error instanceof Error ? error.message : '用户创建失败。');
  } finally {
    createUserSubmitting.value = false;
  }
}

function openResetPasswordModal(user: ManagedAuthUser) {
  resetPasswordForm.userId = user.user_id;
  resetPasswordForm.username = user.username;
  resetPasswordForm.password = '';
  resetPasswordModalVisible.value = true;
}

function closeResetPasswordModal() {
  if (resetPasswordSubmitting.value) return;
  resetPasswordModalVisible.value = false;
}

async function submitResetPassword() {
  if (resetPasswordSubmitting.value) return;

  resetPasswordSubmitting.value = true;
  try {
    const updatedUser = await resetManagedUserPassword(
      resetPasswordForm.userId,
      resetPasswordForm.password
    );
    upsertManagedUser(updatedUser);
    resetPasswordModalVisible.value = false;
    oToast.success('密码已重置，目标账号将被强制重新登录。');
  } catch (error) {
    oToast.error(error instanceof Error ? error.message : '密码重置失败。');
  } finally {
    resetPasswordSubmitting.value = false;
  }
}

async function handleUserRoleChange(
  user: ManagedAuthUser,
  role: 'admin' | 'user'
) {
  if (user.role === role || isPendingUserAction(user.user_id)) return;

  setPendingUserAction(user.user_id, true);
  try {
    const updatedUser = await updateManagedUser(user.user_id, { role });
    upsertManagedUser(updatedUser);
    oToast.success(`已更新 ${user.username} 的角色。`);
  } catch (error) {
    oToast.error(error instanceof Error ? error.message : '更新角色失败。');
  } finally {
    setPendingUserAction(user.user_id, false);
  }
}

async function toggleUserActive(user: ManagedAuthUser) {
  if (isPendingUserAction(user.user_id)) return;

  setPendingUserAction(user.user_id, true);
  try {
    const updatedUser = await updateManagedUser(user.user_id, {
      is_active: !user.is_active
    });
    upsertManagedUser(updatedUser);
    oToast.success(
      user.is_active
        ? `已停用 ${user.username}。`
        : `已重新启用 ${user.username}。`
    );
  } catch (error) {
    oToast.error(error instanceof Error ? error.message : '更新账号状态失败。');
  } finally {
    setPendingUserAction(user.user_id, false);
  }
}

async function refreshHealth() {
  try {
    const response = await fetch(`${apiBase}/health/public`, {
      headers: buildPublicConfigHeaders(form)
    });
    health.value = response.ok ? 'online' : 'offline';
  } catch {
    health.value = 'offline';
  }
}

async function checkProviderHealth(options?: { silent?: boolean }) {
  providerHealthLoading.value = true;

  try {
    const response = await fetch(`${apiBase}/health/providers/public`, {
      headers: buildPublicConfigHeaders(form)
    });
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
    Object.assign(
      form,
      cloneDefaultPublicFrontendConfig(),
      loadPublicFrontendConfig()
    );
    await refreshHealth();
    await checkProviderHealth({ silent: true });
  } catch (error) {
    health.value = 'unknown';
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
    Object.assign(
      form,
      cloneDefaultPublicFrontendConfig(),
      savePublicFrontendConfig(form)
    );
    await refreshHealth();
    await checkProviderHealth({ silent: true });
    notice.value = {
      type: 'success',
      text: '浏览器公开设置已保存，新的请求将自动使用这些参数。'
    };
  } catch (error) {
    health.value = 'unknown';
    notice.value = {
      type: 'error',
      text: error instanceof Error ? error.message : '保存配置失败。'
    };
  } finally {
    saving.value = false;
  }
}

async function resetWebConfig() {
  if (saving.value) return;

  Object.assign(
    form,
    cloneDefaultPublicFrontendConfig(),
    resetPublicFrontendConfig()
  );
  await refreshHealth();
  await checkProviderHealth({ silent: true });
  notice.value = {
    type: 'success',
    text: '浏览器公开设置已恢复默认值。'
  };
}

function toggleAdvanced() {
  advancedExpanded.value = !advancedExpanded.value;
}

onMounted(() => {
  void loadConfig();
  if (isAdminMode.value) {
    void loadManagedUserList({ silent: true });
  }
});

watch(isAdminMode, (nextValue) => {
  if (!nextValue) {
    managedUsers.value = [];
    return;
  }

  if (!managedUsers.value.length) {
    void loadManagedUserList({ silent: true });
  }
});
</script>

<template>
  <div class="o-page-stack">
    <OCard
      padding="lg"
      class="flex items-start justify-between gap-6 max-[960px]:grid max-[960px]:grid-cols-1">
      <div>
        <div
          class="mb-2 text-[11px] font-bold uppercase tracking-[0.08em] text-muted">
          Web Runtime
        </div>
        <h1
          class="m-0 text-[24px] leading-[1.08] font-bold tracking-tight text-heading max-[768px]:text-[22px]">
          公开高级设置
        </h1>
        <p class="mt-1.5 max-w-160 text-[13px] leading-[1.6] text-secondary">
          当前分支为纯 Web
          版本。这里保存的是浏览器侧公开参数，会随请求发送给后端，但不会暴露服务端基础凭据。
        </p>
      </div>
      <div
        class="flex min-w-56 flex-col items-end gap-2 max-[960px]:min-w-0 max-[960px]:items-start">
        <OBadge :variant="getStatusVariant(health)" size="lg">
          <CloudServerOutlined />
          <span>{{ healthText }}</span>
        </OBadge>
      </div>
    </OCard>

    <OCard tone="warning" class="flex items-center gap-4">
      <WarningOutlined class="text-[26px] text-[#9e3328]" />
      <div>
        <h2>当前为纯 Web 模式</h2>
        <p>
          本地壳层、运行时桥接和桌面专属目录管理能力都已移除，当前页面只保留浏览器可安全调整的公开参数。
        </p>
      </div>
    </OCard>

    <OCard v-if="isAdminMode" padding="lg" class="flex flex-col gap-4">
      <div
        class="flex items-start justify-between gap-4 max-[960px]:grid max-[960px]:grid-cols-1">
        <div>
          <div class="text-lg font-bold tracking-[-0.02em] text-zinc-900">
            用户管理
          </div>
          <div class="mt-1.5 text-[13px] leading-[1.7] text-zinc-500">
            管理员可以在这里创建账号、分配管理员权限、停用账号，以及强制重置用户密码。
          </div>
        </div>
        <div class="flex flex-wrap gap-2.5 max-[768px]:w-full">
          <OButton
            variant="secondary"
            :disabled="managedUsersLoading"
            :loading="managedUsersLoading"
            @click="loadManagedUserList()">
            {{ managedUsersLoading ? '刷新中...' : '刷新用户列表' }}
          </OButton>
          <OButton @click="openCreateUserModal">新增用户</OButton>
        </div>
      </div>

      <div class="grid grid-cols-3 gap-3 max-[960px]:grid-cols-1">
        <div class="rounded-2xl border border-black/8 bg-zinc-50 px-4 py-3.5">
          <div
            class="text-xs font-semibold uppercase tracking-[0.08em] text-zinc-500">
            总账号数
          </div>
          <div class="mt-2 text-2xl font-bold text-zinc-900">
            {{ managedUserSummary.total }}
          </div>
        </div>
        <div class="rounded-2xl border border-black/8 bg-zinc-50 px-4 py-3.5">
          <div
            class="text-xs font-semibold uppercase tracking-[0.08em] text-zinc-500">
            启用账号
          </div>
          <div class="mt-2 text-2xl font-bold text-zinc-900">
            {{ managedUserSummary.active }}
          </div>
        </div>
        <div class="rounded-2xl border border-black/8 bg-zinc-50 px-4 py-3.5">
          <div
            class="text-xs font-semibold uppercase tracking-[0.08em] text-zinc-500">
            管理员账号
          </div>
          <div class="mt-2 text-2xl font-bold text-zinc-900">
            {{ managedUserSummary.admins }}
          </div>
        </div>
      </div>

      <div class="grid gap-3">
        <OCard
          v-for="user in managedUsers"
          :key="user.user_id"
          padding="sm"
          :tone="
            !user.is_active
              ? 'muted'
              : user.role === 'admin'
                ? 'success'
                : 'default'
          "
          class="flex flex-col gap-3.5">
          <div
            class="flex items-start justify-between gap-4 max-[960px]:grid max-[960px]:grid-cols-1">
            <div>
              <div class="flex flex-wrap items-center gap-2">
                <div
                  class="text-[16px] font-bold tracking-[-0.01em] text-zinc-900">
                  {{ user.username }}
                </div>
                <span
                  v-if="user.user_id === currentUserId"
                  class="rounded-full bg-black/6 px-2.5 py-1 text-[11px] font-semibold text-zinc-700">
                  当前账号
                </span>
                <span
                  :class="[
                    'rounded-full px-2.5 py-1 text-[11px] font-semibold',
                    user.is_active
                      ? 'bg-[rgba(37,99,65,0.12)] text-[#1f6b42]'
                      : 'bg-black/6 text-zinc-600'
                  ]">
                  {{ formatUserStatus(user.is_active) }}
                </span>
              </div>
              <div class="mt-1.5 text-xs leading-6 text-zinc-500">
                创建于 {{ formatDateTime(user.created_at) }}
              </div>
            </div>

            <div
              class="grid min-w-90 grid-cols-[150px_repeat(2,minmax(0,1fr))] gap-2.5 max-[960px]:min-w-0 max-[960px]:grid-cols-1">
              <OSelect
                :model-value="user.role"
                :options="userRoleOptions"
                :disabled="isPendingUserAction(user.user_id)"
                @update:model-value="
                  handleUserRoleChange(user, $event as 'admin' | 'user')
                " />
              <OButton
                variant="secondary"
                :disabled="isPendingUserAction(user.user_id)"
                @click="openResetPasswordModal(user)">
                重置密码
              </OButton>
              <OButton
                :variant="user.is_active ? 'warning' : 'secondary'"
                :disabled="isPendingUserAction(user.user_id)"
                @click="toggleUserActive(user)">
                {{ user.is_active ? '停用账号' : '重新启用' }}
              </OButton>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
            <span>角色：{{ formatUserRole(user.role) }}</span>
            <span class="text-black/20">/</span>
            <span>最近更新：{{ formatDateTime(user.updated_at) }}</span>
          </div>
        </OCard>

        <OCard
          v-if="!managedUsers.length && !managedUsersLoading"
          padding="sm"
          tone="muted"
          class="text-sm leading-7 text-zinc-500">
          当前没有可管理的用户记录。
        </OCard>
      </div>
    </OCard>

    <OCard padding="lg" class="flex flex-col gap-4">
      <div
        class="flex items-start justify-between gap-4 max-[768px]:grid max-[768px]:grid-cols-1">
        <div>
          <div class="text-lg font-bold tracking-[-0.02em] text-zinc-900">
            生效规则
          </div>
          <div class="mt-1.5 text-[13px] leading-[1.7] text-zinc-500">
            Web
            模式下的公开设置会作为请求级覆盖附带给后端，不修改服务端的基础模型凭据和部署配置。
          </div>
        </div>
        <div
          class="rounded-full border border-black/8 bg-zinc-50 px-3 py-1.5 text-xs font-semibold text-zinc-700">
          当前模式：Web Runtime
        </div>
      </div>

      <div class="grid grid-cols-3 gap-3 max-[960px]:grid-cols-1">
        <div
          v-for="item in effectRuleItems"
          :key="item.title"
          :class="[
            'rounded-2xl border px-4 py-3.5',
            getEffectRuleToneClass(item.tone)
          ]">
          <div class="text-sm font-bold tracking-[-0.01em]">
            {{ item.title }}
          </div>
          <div class="mt-1.5 text-xs leading-6 opacity-90">
            {{ item.detail }}
          </div>
        </div>
      </div>
    </OCard>

    <OCard padding="lg" class="flex flex-col gap-3.5">
      <div
        class="flex cursor-pointer items-center justify-between text-lg font-bold tracking-[-0.02em] text-zinc-900"
        @click="toggleAdvanced">
        <span>公开高级设置</span>
        <DownOutlined
          :class="[
            'transition-transform duration-200',
            advancedExpanded ? 'rotate-180' : ''
          ]" />
      </div>
      <div v-if="advancedExpanded" class="flex flex-col gap-3">
        <p class="text-zinc-500 leading-[1.7]">
          这些参数会保存在当前浏览器，并自动附带到聊天、知识库和来源详情请求中。
        </p>
        <div
          class="rounded-2xl border border-black/8 bg-zinc-50 px-4 py-3 text-xs leading-6 text-zinc-700">
          新参数会在当前浏览器的下一次请求中立即生效。
        </div>

        <div class="flex flex-col gap-4 pt-1.5">
          <OFormSection
            title="请求元信息"
            description="用于向上游网关传递应用来源、应用名称与请求标签等非敏感元信息。下一次请求立即生效。"
            padding="sm"
            class="flex flex-col gap-4">
            <div
              class="grid grid-cols-3 items-start gap-4 max-[960px]:grid-cols-2 max-[768px]:grid-cols-1">
              <OFormItem
                label="请求来源地址"
                help="当上游网关需要识别请求来源站点时使用。多数场景保持默认即可。"
                class="gap-1.5">
                <OInput
                  v-model="form.OPENROUTER_SITE_URL"
                  type="text"
                  placeholder="https://localhost.invalid" />
              </OFormItem>

              <OFormItem
                label="应用名称"
                help="当上游网关需要记录请求来自哪个客户端时使用。"
                class="gap-1.5">
                <OInput
                  v-model="form.OPENROUTER_APP_TITLE"
                  type="text"
                  placeholder="RAG.Agent Web" />
              </OFormItem>

              <OFormItem
                label="请求分类标签"
                help="请求附带的业务标签，用于统计、路由或审计；名称保持通用，不绑定具体供应商。"
                class="col-span-2 gap-1.5 max-[768px]:col-span-1">
                <OInput
                  v-model="form.OPENROUTER_CATEGORIES"
                  type="text"
                  placeholder="general-chat" />
              </OFormItem>
            </div>
          </OFormSection>

          <OFormSection
            title="Embedding 策略"
            description="控制向量化 provider、token 统计方式与切分上限。下一次上传与向量化请求立即生效。"
            padding="sm"
            class="flex flex-col gap-4">
            <div
              class="grid grid-cols-3 items-start gap-4 max-[960px]:grid-cols-2 max-[768px]:grid-cols-1">
              <OFormItem
                label="Embedding Provider"
                help="LiteLLM 调用 embedding 时使用的 provider 标识。OpenAI 兼容接口通常填 openai。"
                class="gap-1.5">
                <OInput
                  v-model="form.EMBEDDING_PROVIDER"
                  type="text"
                  placeholder="openai" />
              </OFormItem>

              <OFormItem
                label="Embedding 最大输入 Token"
                help="单段文本允许进入嵌入接口的最大 token 数，超过后会自动继续切分。"
                class="gap-1.5">
                <OInput
                  v-model="form.EMBEDDING_MAX_INPUT_TOKENS"
                  type="number"
                  min="1"
                  step="1"
                  placeholder="512" />
              </OFormItem>

              <OFormItem
                label="Embedding 目标分块 Token"
                help="二次切分时的目标大小。建议小于最大输入 token，上调会减少 chunk 数。"
                class="gap-1.5">
                <OInput
                  v-model="form.EMBEDDING_TARGET_CHUNK_TOKENS"
                  type="number"
                  min="1"
                  step="1"
                  placeholder="384" />
              </OFormItem>

              <OFormItem
                label="Embedding 重叠 Token"
                help="相邻分块之间保留的上下文 token 数，用于降低切分边界带来的信息断裂。"
                class="gap-1.5">
                <OInput
                  v-model="form.EMBEDDING_CHUNK_OVERLAP_TOKENS"
                  type="number"
                  min="0"
                  step="1"
                  placeholder="48" />
              </OFormItem>

              <OFormItem
                label="Embedding Tokenizer Model"
                help="用于 token 计数的模型标识；留空时默认跟随当前 embedding model。"
                class="gap-1.5">
                <OInput
                  v-model="form.EMBEDDING_TOKENIZER_MODEL"
                  type="text"
                  placeholder="留空时跟随 embedding provider 配置" />
              </OFormItem>

              <OFormItem
                label="Embedding Tokenizer Encoding"
                help="tokenizer model 无法直接识别时使用的编码兜底值。"
                class="gap-1.5">
                <OInput
                  v-model="form.EMBEDDING_TOKENIZER_ENCODING"
                  type="text"
                  placeholder="cl100k_base" />
              </OFormItem>
            </div>
          </OFormSection>

          <OFormSection
            title="检索策略"
            description="控制召回、重排、上下文保留与问题扩写数量。下一次聊天检索请求立即生效。"
            padding="sm"
            class="flex flex-col gap-4">
            <div
              class="grid grid-cols-3 items-start gap-4 max-[960px]:grid-cols-2 max-[768px]:grid-cols-1">
              <OFormItem
                label="Reranker Timeout"
                help="重排请求超时时间，单位秒，用于控制直连 rerank 接口的等待上限。"
                class="gap-1.5">
                <OInput
                  v-model="form.RERANKER_REQUEST_TIMEOUT"
                  type="number"
                  min="1"
                  step="1"
                  placeholder="20" />
              </OFormItem>

              <OFormItem
                label="召回候选数量"
                help="每次检索阶段先召回多少个候选片段。多知识库场景下适当调高有助于减少漏召回。"
                class="gap-1.5">
                <OInput
                  v-model="form.RETRIEVAL_CANDIDATE_LIMIT"
                  type="number"
                  min="1"
                  step="1"
                  placeholder="12" />
              </OFormItem>

              <OFormItem
                label="最终上下文数量"
                help="重排后最多保留多少个片段进入答案上下文。值越高，引用更充分，但生成成本也会上升。"
                class="gap-1.5">
                <OInput
                  v-model="form.RETRIEVAL_FINAL_CONTEXT_LIMIT"
                  type="number"
                  min="1"
                  step="1"
                  placeholder="3" />
              </OFormItem>

              <OFormItem
                label="引用来源数量"
                help="回答完成后最多展示多少条引用来源。建议与最终上下文数量保持一致或略小。"
                class="gap-1.5">
                <OInput
                  v-model="form.RETRIEVAL_SOURCE_LIMIT"
                  type="number"
                  min="1"
                  step="1"
                  placeholder="3" />
              </OFormItem>

              <OFormItem
                label="问题扩写数量"
                help="口语问题会先扩写出多少个更正式的相近问法再做召回。填 0 表示关闭扩写。"
                class="gap-1.5">
                <OInput
                  v-model="form.RETRIEVAL_QUERY_EXPANSION_COUNT"
                  type="number"
                  min="0"
                  step="1"
                  placeholder="2" />
              </OFormItem>

              <OFormItem
                label="回答温度"
                help="控制回答稳定性与发散度。值越低越稳，越高越灵活。"
                class="gap-1.5">
                <OInput
                  v-model="form.CHAT_TEMPERATURE"
                  type="number"
                  min="0"
                  max="1"
                  step="0.1"
                  placeholder="0" />
              </OFormItem>
            </div>
          </OFormSection>
        </div>
      </div>
    </OCard>

    <OCard padding="lg" class="flex flex-col gap-4">
      <div>
        <div class="text-lg font-bold tracking-[-0.02em] text-zinc-900">
          反思策略
        </div>
        <div class="mt-1.5 text-[13px] leading-[1.7] text-zinc-500">
          控制回答前的 reflection 校验强度。弱模型容易因为 reflection
          不完整而被直接拦截，这里可以按模型能力快速切换策略。
        </div>
      </div>

      <div class="grid gap-4 max-[960px]:grid-cols-1">
        <!-- <OFormItem
          label="Reflection Tokens"
          help="填 0 表示关闭反思拦截；其他值越大，模型越容易输出完整 reflection 判定。"
          class="gap-1.5">
          <OInput
            v-model="form.REFLECTION_TOKENS"
            type="number"
            min="0"
            step="1"
            placeholder="256" />
        </OFormItem> -->

        <div
          class="grid grid-cols-4 gap-2.5 max-[1200px]:grid-cols-2 max-[768px]:grid-cols-1">
          <button
            v-for="preset in reflectionTokenPresets"
            :key="preset.value"
            type="button"
            :class="[
              'rounded-2xl border px-4 py-3 text-left transition-all duration-200',
              isReflectionPresetActive(preset.value)
                ? 'border-[rgba(37,99,65,0.28)] bg-[rgba(37,99,65,0.09)] shadow-[0_8px_20px_rgba(37,99,65,0.08)]'
                : 'border-black/8 bg-zinc-50 hover:border-black/14 hover:bg-white'
            ]"
            @click="applyReflectionPreset(preset.value)">
            <div class="flex items-center justify-between gap-3">
              <span class="text-sm font-bold text-zinc-900">
                {{ preset.label }}
              </span>
              <span
                :class="[
                  'rounded-full px-2.5 py-1 text-[11px] font-semibold',
                  isReflectionPresetActive(preset.value)
                    ? 'bg-[rgba(37,99,65,0.14)] text-[#1f6b42]'
                    : 'bg-black/6 text-zinc-600'
                ]">
                {{ preset.value }}
              </span>
            </div>
            <div class="mt-2 text-xs leading-6 text-zinc-600">
              {{ preset.detail }}
            </div>
          </button>
        </div>
      </div>
    </OCard>

    <OCard padding="lg" class="flex flex-col gap-4">
      <section class="flex flex-col gap-3">
        <div
          class="flex items-start justify-between gap-4 max-[768px]:grid max-[768px]:grid-cols-1">
          <div>
            <div class="text-lg font-bold tracking-[-0.02em] text-zinc-900">
              Provider 检测
            </div>
            <div class="mt-1.5 text-[13px] text-zinc-500">
              Web 端显示脱敏后的 Provider 检测结果，不返回服务端敏感配置明细。
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
            class="flex flex-col gap-2.5">
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
          {{ saving ? '正在保存浏览器设置...' : '保存浏览器设置' }}
        </OButton>
        <OButton variant="secondary" :disabled="saving" @click="resetWebConfig">
          恢复默认设置
        </OButton>
      </div>
    </OCard>

    <OModal
      :visible="createUserModalVisible"
      title="新增用户"
      subtitle="创建账号后，管理员可继续调整角色与状态。"
      cancel-text="取消"
      confirm-text="创建用户"
      :confirm-loading="createUserSubmitting"
      @close="closeCreateUserModal"
      @confirm="submitCreateUser">
      <div class="grid gap-4">
        <OFormItem label="用户名" help="至少 3 个字符，系统会统一转成小写。">
          <OInput
            v-model="createUserForm.username"
            type="text"
            placeholder="alice" />
        </OFormItem>
        <OFormItem label="初始密码" help="至少 6 个字符。首次登录后可再重置。">
          <OInput
            v-model="createUserForm.password"
            type="password"
            placeholder="请输入初始密码" />
        </OFormItem>
        <OFormItem label="角色">
          <OSelect v-model="createUserForm.role" :options="userRoleOptions" />
        </OFormItem>
      </div>
    </OModal>

    <OModal
      :visible="resetPasswordModalVisible"
      title="重置密码"
      :subtitle="`为 ${resetPasswordForm.username || '该用户'} 设置新密码，并立即使旧登录态失效。`"
      cancel-text="取消"
      confirm-text="确认重置"
      confirm-variant="warning"
      :confirm-loading="resetPasswordSubmitting"
      @close="closeResetPasswordModal"
      @confirm="submitResetPassword">
      <div class="grid gap-4">
        <OFormItem label="目标用户">
          <div
            class="rounded-2xl border border-black/8 bg-zinc-50 px-4 py-3 text-sm font-medium text-zinc-800">
            {{ resetPasswordForm.username || '—' }}
          </div>
        </OFormItem>
        <OFormItem label="新密码" help="密码更新后，目标账号需要重新登录。">
          <OInput
            v-model="resetPasswordForm.password"
            type="password"
            placeholder="请输入新密码" />
        </OFormItem>
      </div>
    </OModal>
  </div>
</template>
