<script setup lang="ts">
defineOptions({
  name: 'SettingsView'
});

import { computed, onMounted, reactive, ref, watch } from 'vue';
import {
  CheckCircleOutlined,
  CloudServerOutlined,
  WarningOutlined
} from '@ant-design/icons-vue';
import { getApiBase } from '@/services/runtime';
import {
  createManagedUser,
  fetchManagedUsers,
  resetManagedUserPassword,
  updateManagedUser,
  useAuthState,
  type ManagedAuthUser,
  type ManagedUserListResult
} from '@/services/auth';
import {
  buildPublicConfigHeaders,
  createEmptyPublicFrontendConfig,
  loadPublicFrontendConfig,
  loadSystemPublicFrontendConfig,
  resetPublicFrontendConfig,
  resetSystemPublicFrontendConfig,
  savePublicFrontendConfig,
  saveSystemPublicFrontendConfig,
  type PublicFrontendConfig
} from '@/services/publicConfig';
import {
  OBadge,
  OButton,
  OCard,
  OFormItem,
  OInput,
  OModal,
  OSelect,
  useOToast
} from '@/orange-ui';
import { cn } from '@/utils/cn';

const apiBase = getApiBase();
const activeTab = ref<
  'embedding' | 'retrieval' | 'chat' | 'reflection' | 'status' | 'users'
>('status');
const adminConfigPanel = ref<'system' | 'user'>('system');

const authState = useAuthState();
const form = reactive<PublicFrontendConfig>(createEmptyPublicFrontendConfig());
const loading = ref(false);
const saving = ref(false);
const health = ref<'unknown' | 'online' | 'offline'>('unknown');
const notice = ref<{ type: 'success' | 'error'; text: string } | null>(null);
const providerHealthLoading = ref(false);
const providerHealth = ref<Record<string, ProviderHealthItem>>({});
const managedUsers = ref<ManagedAuthUser[]>([]);
const managedUsersLoading = ref(false);
const managedUsersTotal = ref(0);
const managedUsersActiveTotal = ref(0);
const managedUsersAdminTotal = ref(0);
const managedUsersPage = ref(1);
const managedUsersPageSize = ref(6);
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

interface ReflectionTokenPreset {
  label: string;
  value: number;
  detail: string;
}

interface SettingsModuleTab {
  key: 'embedding' | 'retrieval' | 'chat' | 'reflection';
  label: string;
}

const healthText = computed(() => {
  if (health.value === 'online') return '后端服务运行中';
  if (health.value === 'offline') return '后端服务不可用';
  return '等待检测服务状态';
});

const isAdminMode = computed(() => authState.session?.user.role === 'admin');
const hasEditableConfigAccess = computed(() =>
  Boolean(authState.session?.user.user_id)
);
const isEditingSystemDefaults = computed(
  () => isAdminMode.value && adminConfigPanel.value === 'system'
);
const currentUserId = computed(() =>
  String(authState.session?.user.user_id || '')
);
const settingsPageTitle = computed(() => {
  if (isAdminMode.value) return '系统高级设置';
  if (hasEditableConfigAccess.value) return '我的高级设置';
  return '系统运行状态';
});
const settingsPageDescription = computed(() => {
  if (isAdminMode.value) {
    return '管理员可在这里切换维护系统默认配置和自己的个人配置。系统默认配置会作为所有用户的统一默认值与重置回退基线。';
  }

  if (hasEditableConfigAccess.value) {
    return '这里保存的是当前账号的个人配置。请求会优先使用你的个人配置；未覆盖的字段继续继承管理员默认值。';
  }

  return '未登录状态下只能查看运行状态，不能读取或修改数据库中的运行参数。';
});
const configCardDescription = computed(() => {
  if (isEditingSystemDefaults.value) {
    return '管理员修改的是系统默认值。普通用户点击重置时，会回退到这里保存的默认配置，而不是代码内置值。';
  }

  return '个人配置只对当前账号生效，不会影响其他用户。重置后会删除个人覆盖项，并重新继承管理员默认值。';
});
const saveButtonText = computed(() =>
  isEditingSystemDefaults.value ? '保存系统默认配置' : '保存我的配置'
);
const savingButtonText = computed(() =>
  isEditingSystemDefaults.value
    ? '正在保存系统默认配置...'
    : '正在保存我的配置...'
);
const resetButtonText = computed(() =>
  isEditingSystemDefaults.value ? '恢复初始化默认' : '恢复系统默认'
);
const configPanelBadgeText = computed(() =>
  isEditingSystemDefaults.value ? '当前面板：系统默认值' : '当前面板：我的配置'
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

const settingsModuleTabs: SettingsModuleTab[] = [
  {
    key: 'embedding',
    label: 'Embedding'
  },
  {
    key: 'retrieval',
    label: '检索策略'
  },
  {
    key: 'chat',
    label: 'Chat'
  },
  {
    key: 'reflection',
    label: '反思策略'
  }
];

const isPublicSettingsTab = computed(() =>
  settingsModuleTabs.some((item) => item.key === activeTab.value)
);

const managedUserSummary = computed(() => {
  return {
    total: managedUsersTotal.value,
    active: managedUsersActiveTotal.value,
    admins: managedUsersAdminTotal.value
  };
});

const managedUserTotalPages = computed(() =>
  Math.max(1, Math.ceil(managedUsersTotal.value / managedUsersPageSize.value))
);

const managedUserRangeText = computed(() => {
  if (!managedUsersTotal.value || !managedUsers.value.length) {
    return '当前没有可管理的用户记录。';
  }

  const start = (managedUsersPage.value - 1) * managedUsersPageSize.value + 1;
  const end = start + managedUsers.value.length - 1;
  return `显示第 ${start}-${end} 条，共 ${managedUsersTotal.value} 条`;
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
    return 'bg-success-soft text-success';
  }

  if (
    status === 'missing_config' ||
    status === 'timeout' ||
    status === 'network_error' ||
    status === 'upstream_error'
  ) {
    return 'bg-warning-soft text-warning';
  }

  if (status === 'auth_error') {
    return 'bg-danger-soft text-danger';
  }

  return 'bg-warning-soft text-warning';
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

function getProviderHeadline(item?: ProviderHealthItem) {
  if (!item) return '尚未执行检测';
  if (item.status === 'ok') {
    return item.configured ? '连接已验证，模型信息已脱敏' : '配置未公开';
  }
  if (item.status === 'missing_config') return '配置缺失';
  if (!item.configured) return '配置未完成';
  return '检测已返回异常';
}

function getProviderFootnote(item?: ProviderHealthItem) {
  if (!item) return '—';
  if (item.status === 'ok') return '公开检测视图不展示模型名和 Base URL';
  return item.configured
    ? '检测明细已脱敏，仅保留状态摘要'
    : '请先补齐该能力所需配置';
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

function updateManagedUserList(result: ManagedUserListResult) {
  managedUsers.value = result.items;
  managedUsersTotal.value = result.total;
  managedUsersActiveTotal.value = result.active_total;
  managedUsersAdminTotal.value = result.admin_total;
  managedUsersPage.value = result.page;
  managedUsersPageSize.value = result.page_size;
}

async function loadManagedUserList(options?: { silent?: boolean }) {
  if (!isAdminMode.value) return;

  managedUsersLoading.value = true;
  try {
    const result = await fetchManagedUsers({
      page: managedUsersPage.value,
      pageSize: managedUsersPageSize.value
    });
    updateManagedUserList(result);
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

async function changeManagedUsersPage(nextPage: number) {
  const normalizedPage = Math.min(
    Math.max(1, nextPage),
    managedUserTotalPages.value
  );
  if (normalizedPage === managedUsersPage.value || managedUsersLoading.value) {
    return;
  }

  managedUsersPage.value = normalizedPage;
  await loadManagedUserList({ silent: true });
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
    await createManagedUser({
      username: createUserForm.username,
      password: createUserForm.password,
      role: createUserForm.role
    });
    await loadManagedUserList({ silent: true });
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
    await resetManagedUserPassword(
      resetPasswordForm.userId,
      resetPasswordForm.password
    );
    await loadManagedUserList({ silent: true });
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
    await updateManagedUser(user.user_id, { role });
    await loadManagedUserList({ silent: true });
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
    await updateManagedUser(user.user_id, {
      is_active: !user.is_active
    });
    await loadManagedUserList({ silent: true });
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
      headers: hasEditableConfigAccess.value
        ? buildPublicConfigHeaders(form)
        : buildPublicConfigHeaders()
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
      headers: hasEditableConfigAccess.value
        ? buildPublicConfigHeaders(form)
        : buildPublicConfigHeaders()
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
  if (!hasEditableConfigAccess.value) return;

  loading.value = true;
  notice.value = null;

  try {
    Object.assign(
      form,
      isEditingSystemDefaults.value
        ? await loadSystemPublicFrontendConfig()
        : await loadPublicFrontendConfig()
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
  if (!hasEditableConfigAccess.value || saving.value) return;

  saving.value = true;
  notice.value = null;

  try {
    Object.assign(
      form,
      isEditingSystemDefaults.value
        ? await saveSystemPublicFrontendConfig(form)
        : await savePublicFrontendConfig(form)
    );
    await refreshHealth();
    await checkProviderHealth({ silent: true });
    notice.value = {
      type: 'success',
      text: isEditingSystemDefaults.value
        ? '系统默认配置已保存，后续请求会使用新的管理员默认值。'
        : '个人配置已保存，当前账号后续请求会优先使用新的配置。'
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
  if (!hasEditableConfigAccess.value || saving.value) return;

  Object.assign(
    form,
    isEditingSystemDefaults.value
      ? await resetSystemPublicFrontendConfig()
      : await resetPublicFrontendConfig()
  );
  await refreshHealth();
  await checkProviderHealth({ silent: true });
  notice.value = {
    type: 'success',
    text: isEditingSystemDefaults.value
      ? '系统默认配置已恢复到数据库初始化默认值。'
      : '个人配置已清空，当前账号重新继承管理员默认值。'
  };
}

onMounted(() => {
  if (hasEditableConfigAccess.value) {
    activeTab.value = 'embedding';
    void loadConfig();
  } else {
    void refreshHealth();
    void checkProviderHealth({ silent: true });
  }
  if (isAdminMode.value) {
    void loadManagedUserList({ silent: true });
  }
});

watch(adminConfigPanel, () => {
  if (!isAdminMode.value || !isPublicSettingsTab.value) return;
  void loadConfig();
});

watch(
  () => authState.session?.user.role ?? '',
  (nextRole) => {
    if (!nextRole) {
      managedUsers.value = [];
      managedUsersTotal.value = 0;
      managedUsersActiveTotal.value = 0;
      managedUsersAdminTotal.value = 0;
      managedUsersPage.value = 1;
      adminConfigPanel.value = 'system';
      activeTab.value = 'status';
      Object.assign(form, createEmptyPublicFrontendConfig());
      void refreshHealth();
      void checkProviderHealth({ silent: true });
      return;
    }

    if (nextRole !== 'admin') {
      managedUsers.value = [];
      managedUsersTotal.value = 0;
      managedUsersActiveTotal.value = 0;
      managedUsersAdminTotal.value = 0;
      managedUsersPage.value = 1;
      adminConfigPanel.value = 'system';
      if (activeTab.value === 'users') {
        activeTab.value = 'embedding';
      }
    }

    if (activeTab.value === 'status') {
      activeTab.value = 'embedding';
    }

    void loadConfig();

    if (nextRole === 'admin' && !managedUsers.value.length) {
      void loadManagedUserList({ silent: true });
    }
  }
);
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
          {{ settingsPageTitle }}
        </h1>
        <p class="mt-1.5 max-w-160 text-[13px] leading-[1.6] text-secondary">
          当前分支为纯 Web 版本。{{ settingsPageDescription }}
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

    <OCard
      v-if="!hasEditableConfigAccess"
      tone="muted"
      class="text-sm leading-7 text-zinc-500">
      当前未登录，只能查看运行状态。登录后可读取自己的生效配置；管理员额外拥有系统默认配置维护权限。
    </OCard>

    <div
      class="mb-4 mt-2 flex flex-wrap items-center gap-1 border-b border-border/60">
      <button
        v-if="hasEditableConfigAccess"
        v-for="item in settingsModuleTabs"
        :key="item.key"
        type="button"
        @click="activeTab = item.key"
        :class="[
          'px-5 py-3 border-b-2 text-[15px] font-medium transition-colors outline-none',
          activeTab === item.key
            ? 'border-zinc-900 text-zinc-900'
            : 'border-transparent text-text-secondary hover:text-text hover:border-border-soft'
        ]">
        {{ item.label }}
      </button>
      <button
        type="button"
        @click="activeTab = 'status'"
        :class="[
          'px-5 py-3 border-b-2 text-[15px] font-medium transition-colors outline-none',
          activeTab === 'status'
            ? 'border-zinc-900 text-zinc-900'
            : 'border-transparent text-text-secondary hover:text-text hover:border-border-soft'
        ]">
        运行状态
      </button>
      <button
        v-if="isAdminMode"
        type="button"
        @click="activeTab = 'users'"
        :class="[
          'px-5 py-3 border-b-2 text-[15px] font-medium transition-colors outline-none',
          activeTab === 'users'
            ? 'border-zinc-900 text-zinc-900'
            : 'border-transparent text-text-secondary hover:text-text hover:border-border-soft'
        ]">
        用户管理
      </button>
    </div>

    <OCard
      v-show="activeTab === 'users' && isAdminMode"
      padding="lg"
      class="flex flex-col gap-4">
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

      <div
        class="flex items-center justify-between gap-3 rounded-2xl border border-black/8 bg-zinc-50 px-4 py-3 text-sm text-zinc-600 max-[768px]:flex-col max-[768px]:items-start">
        <span>{{ managedUserRangeText }}</span>
        <span>第 {{ managedUsersPage }} / {{ managedUserTotalPages }} 页</span>
      </div>

      <div class="grid gap-2.5">
        <div
          v-for="user in managedUsers"
          :key="user.user_id"
          :class="[
            'grid grid-cols-[minmax(0,1.6fr)_160px_minmax(220px,1fr)] items-center gap-4 rounded-2xl border px-4 py-3',
            !user.is_active
              ? 'border-border bg-surface-soft'
              : user.role === 'admin'
                ? 'border-success-border bg-success-soft/50'
                : 'border-black/8 bg-white',
            'max-[1080px]:grid-cols-1'
          ]">
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <div
                class="truncate text-[16px] font-bold tracking-[-0.01em] text-zinc-900">
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
                    ? 'bg-success-soft text-success'
                    : 'bg-surface-muted text-text-secondary'
                ]">
                {{ formatUserStatus(user.is_active) }}
              </span>
            </div>
            <div class="mt-1 text-xs leading-6 text-zinc-500">
              <span>角色：{{ formatUserRole(user.role) }}</span>
              <span class="mx-2 text-black/20">/</span>
              <span>创建于 {{ formatDateTime(user.created_at) }}</span>
              <span class="mx-2 text-black/20">/</span>
              <span>最近更新 {{ formatDateTime(user.updated_at) }}</span>
            </div>
          </div>

          <div class="min-w-0 max-[1080px]:max-w-60">
            <OSelect
              :model-value="user.role"
              :options="userRoleOptions"
              :disabled="isPendingUserAction(user.user_id)"
              @update:model-value="
                handleUserRoleChange(user, $event as 'admin' | 'user')
              " />
          </div>

          <div
            class="flex flex-wrap justify-end gap-2 max-[1080px]:justify-start">
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

        <OCard
          v-if="!managedUsers.length && !managedUsersLoading"
          padding="sm"
          tone="muted"
          class="text-sm leading-7 text-zinc-500">
          当前没有可管理的用户记录。
        </OCard>
      </div>

      <div
        v-if="managedUsersTotal > managedUsersPageSize"
        class="flex items-center justify-between gap-3 max-[768px]:flex-col max-[768px]:items-stretch">
        <div class="text-xs text-zinc-500">
          每页 {{ managedUsersPageSize }} 条
        </div>
        <div class="flex items-center gap-2 max-[768px]:justify-between">
          <OButton
            variant="secondary"
            size="sm"
            :disabled="managedUsersLoading || managedUsersPage <= 1"
            @click="changeManagedUsersPage(managedUsersPage - 1)">
            上一页
          </OButton>
          <div class="text-sm font-medium text-zinc-700">
            第 {{ managedUsersPage }} / {{ managedUserTotalPages }} 页
          </div>
          <OButton
            variant="secondary"
            size="sm"
            :disabled="
              managedUsersLoading || managedUsersPage >= managedUserTotalPages
            "
            @click="changeManagedUsersPage(managedUsersPage + 1)">
            下一页
          </OButton>
        </div>
      </div>
    </OCard>

    <OCard
      v-show="isPublicSettingsTab && hasEditableConfigAccess"
      padding="lg"
      class="flex flex-col gap-3.5">
      <div
        v-if="isAdminMode"
        class="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-black/8 bg-zinc-50 px-4 py-3">
        <div>
          <div class="text-[15px] font-bold tracking-[-0.01em] text-zinc-900">
            配置面板
          </div>
          <div class="mt-1 text-[13px] leading-6 text-zinc-500">
            管理员可以分别维护系统默认值和自己的个人配置，两者互不覆盖。
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <span
            class="rounded-full bg-black/6 px-3 py-1.5 text-[11px] font-semibold text-zinc-700">
            {{ configPanelBadgeText }}
          </span>
          <button
            type="button"
            @click="adminConfigPanel = 'system'"
            :class="[
              'rounded-full border px-3.5 py-2 text-[13px] font-semibold transition-colors',
              adminConfigPanel === 'system'
                ? 'border-zinc-900 bg-zinc-900 text-white'
                : 'border-black/10 bg-white text-zinc-700 hover:border-black/20'
            ]">
            系统默认值
          </button>
          <button
            type="button"
            @click="adminConfigPanel = 'user'"
            :class="[
              'rounded-full border px-3.5 py-2 text-[13px] font-semibold transition-colors',
              adminConfigPanel === 'user'
                ? 'border-zinc-900 bg-zinc-900 text-white'
                : 'border-black/10 bg-white text-zinc-700 hover:border-black/20'
            ]">
            我的配置
          </button>
        </div>
      </div>

      <div
        class="rounded-2xl border border-black/8 bg-zinc-50 px-4 py-3 text-[13px] leading-7 text-zinc-600">
        {{ configCardDescription }}
      </div>

      <div class="flex flex-col gap-4 pt-1.5">
        <div
          v-show="activeTab === 'embedding'"
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

        <div
          v-show="activeTab === 'retrieval'"
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
        </div>

        <div
          v-show="activeTab === 'chat'"
          class="grid grid-cols-3 items-start gap-4 max-[960px]:grid-cols-2 max-[768px]:grid-cols-1">
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

          <OFormItem
            label="OpenRouter Site URL"
            help="当 Chat Base URL 指向 OpenRouter 时，下发到 HTTP-Referer 请求头。"
            class="gap-1.5">
            <OInput
              v-model="form.OPENROUTER_SITE_URL"
              type="text"
              placeholder="http://localhost:5173" />
          </OFormItem>

          <OFormItem
            label="OpenRouter App Title"
            help="当 Chat Base URL 指向 OpenRouter 时，下发到 X-OpenRouter-Title 请求头。"
            class="gap-1.5">
            <OInput
              v-model="form.OPENROUTER_APP_TITLE"
              type="text"
              placeholder="RAG.Agent Local" />
          </OFormItem>

          <OFormItem
            label="OpenRouter Categories"
            help="当 Chat Base URL 指向 OpenRouter 时，下发到 X-OpenRouter-Categories 请求头。多个值可用英文逗号分隔。"
            class="gap-1.5">
            <OInput
              v-model="form.OPENROUTER_CATEGORIES"
              type="text"
              placeholder="general-chat" />
          </OFormItem>
        </div>

        <div
          v-show="activeTab === 'reflection'"
          class="grid grid-cols-4 gap-2.5 max-[1200px]:grid-cols-2 max-[768px]:grid-cols-1">
          <button
            v-for="preset in reflectionTokenPresets"
            :key="preset.value"
            type="button"
            :class="[
              'rounded-2xl border px-4 py-3 text-left transition-all duration-200',
              isReflectionPresetActive(preset.value)
                ? 'border-success-border bg-success-soft shadow-sm'
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
                    ? 'bg-success-soft text-success'
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

        <div class="flex flex-wrap gap-3 max-[768px]:flex-col">
          <OButton
            :disabled="loading || saving"
            :loading="saving"
            @click="saveConfig">
            {{ saving ? savingButtonText : saveButtonText }}
          </OButton>
          <OButton
            variant="secondary"
            :disabled="saving"
            @click="resetWebConfig">
            {{ resetButtonText }}
          </OButton>
        </div>
      </div>
    </OCard>

    <OCard
      v-show="activeTab === 'status'"
      padding="lg"
      class="flex flex-col gap-4">
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
                  {{ getProviderHeadline(entry.item) }}
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
              {{ getProviderFootnote(entry.item) }}
            </div>
          </OCard>
        </div>
      </section>
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
