<script setup lang="ts">
defineOptions({
  name: 'LoginView'
});

import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  LockOutlined,
  UserOutlined,
  RobotOutlined
} from '@ant-design/icons-vue';
import { OButton, OCard, OFormItem, OInput, useOToast } from '@/orange-ui';
import { getApiBase } from '@/services/runtime';
import {
  saveAuthSession,
  type AuthSession,
  type AuthFeatures
} from '@/services/auth';

interface AuthApiResponse {
  token: string;
  expires_at: string;
  user: AuthSession['user'];
  features: AuthFeatures;
}

const router = useRouter();
const route = useRoute();
const oToast = useOToast();

const loading = ref(false);
const bootstrapLoading = ref(false);
const registerMode = ref(false);
const features = ref<AuthFeatures>({
  private_knowledge_base_enabled: true,
  open_registration_enabled: false
});

const form = reactive({
  username: '',
  password: ''
});

const pageTitle = computed(() =>
  registerMode.value ? '创建账号' : '账号登录'
);
const submitText = computed(() =>
  registerMode.value ? '注册并进入' : '登录并进入'
);
const redirectPath = computed(() => {
  const rawRedirect = String(route.query.redirect || '').trim();
  return rawRedirect.startsWith('/') ? rawRedirect : '/';
});

async function loadBootstrap() {
  bootstrapLoading.value = true;
  try {
    const response = await fetch(`${getApiBase()}/api/auth/bootstrap`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const payload = (await response.json()) as {
      features?: AuthFeatures;
    };
    features.value = payload.features || features.value;
  } catch (error) {
    oToast.error(error instanceof Error ? error.message : '初始化登录页失败');
  } finally {
    bootstrapLoading.value = false;
  }
}

async function submit() {
  if (loading.value) {
    return;
  }

  const username = form.username.trim();
  const password = form.password;
  if (!username || !password) {
    oToast.error('请先填写用户名和密码');
    return;
  }

  loading.value = true;
  try {
    const endpoint = registerMode.value
      ? '/api/auth/register'
      : '/api/auth/login';
    const response = await fetch(`${getApiBase()}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ username, password })
    });
    const payload = (await response.json()) as AuthApiResponse & {
      detail?: string;
    };
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }

    saveAuthSession({
      token: payload.token,
      expires_at: payload.expires_at,
      user: payload.user,
      features: payload.features
    });
    await router.replace(redirectPath.value);
  } catch (error) {
    oToast.error(error instanceof Error ? error.message : '登录失败');
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadBootstrap();
});
</script>

<template>
  <div
    class="relative flex min-h-[calc(100vh-6rem)] w-full flex-col items-center justify-center p-4">
    <div
      class="pointer-events-none absolute left-1/2 top-1/2 -z-10 h-[800px] w-full max-w-[1000px] -translate-x-1/2 -translate-y-1/2 overflow-hidden opacity-40">
      <div
        class="absolute left-[20%] top-[20%] h-96 w-96 rounded-full bg-blue-400/20 mix-blend-multiply blur-[100px] filter" />
      <div
        class="absolute right-[20%] top-[30%] h-96 w-96 rounded-full bg-indigo-400/20 mix-blend-multiply blur-[100px] filter" />
      <div
        class="absolute bottom-[20%] left-[33%] h-96 w-96 rounded-full bg-purple-400/20 mix-blend-multiply blur-[100px] filter" />
    </div>

    <div class="z-10 w-full max-w-[400px]">
      <div class="mb-8 flex flex-col items-center text-center">
        <div
          class="mb-6 flex h-[60px] w-[60px] items-center justify-center rounded-2xl border border-black/[0.08] bg-white text-zinc-900 shadow-xl shadow-black/5">
          <RobotOutlined class="text-3xl" />
        </div>
        <h1 class="text-2xl font-bold tracking-tight text-zinc-900">
          {{ pageTitle }}
        </h1>
        <p class="mt-2 text-sm text-zinc-500">
          {{ bootstrapLoading ? '加载配置中...' : '欢迎来到 RAG.Agent 工作台' }}
        </p>
      </div>

      <OCard
        padding="lg"
        class="border-white/60 bg-white/70 shadow-2xl shadow-zinc-200/50 backdrop-blur-xl">
        <div class="flex flex-col gap-6">
          <div class="flex flex-col gap-4">
            <OFormItem label="用户名" :required="true">
              <OInput
                v-model="form.username"
                :disabled="loading"
                placeholder="请输入用户名"
                class="bg-white/80">
                <template #prefix>
                  <UserOutlined class="text-zinc-400" />
                </template>
              </OInput>
            </OFormItem>

            <OFormItem label="密码" :required="true">
              <OInput
                v-model="form.password"
                type="password"
                :disabled="loading"
                placeholder="请输入密码"
                class="bg-white/80"
                @keydown.enter="submit">
                <template #prefix>
                  <LockOutlined class="text-zinc-400" />
                </template>
              </OInput>
            </OFormItem>
          </div>

          <div class="flex flex-col gap-3">
            <OButton
              block
              :loading="loading"
              class="h-11 text-[15px]"
              @click="submit">
              {{ submitText }}
            </OButton>
            <OButton
              v-if="features.open_registration_enabled"
              block
              variant="ghost"
              :disabled="loading"
              @click="registerMode = !registerMode">
              {{ registerMode ? '已有账号，返回登录' : '没有账号，前往注册' }}
            </OButton>
          </div>

          <div
            v-if="!registerMode"
            class="mt-1 rounded-xl border border-orange-100 bg-orange-50/50 px-4 py-3">
            <p class="text-[12px] leading-[1.6] text-orange-800/80">
              普通用户账号需由管理员创建。默认管理员账号由后端自动初始化，请首次部署后尽快修改默认凭据。
            </p>
          </div>
        </div>
      </OCard>
    </div>
  </div>
</template>
