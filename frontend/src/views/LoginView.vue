<script setup lang="ts">
defineOptions({
  name: 'LoginView'
});

import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { LockOutlined, UserOutlined } from '@ant-design/icons-vue';
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
    class="flex min-h-[calc(100vh-8rem)] items-center justify-center px-4 py-8">
    <div class="grid w-full max-w-5xl gap-6 lg:grid-cols-[1.2fr_0.9fr]">
      <OCard
        padding="lg"
        class="relative overflow-hidden border-black/8 bg-[radial-gradient(circle_at_top_left,rgba(240,181,77,0.18),transparent_32%),linear-gradient(135deg,rgba(255,252,246,0.98),rgba(247,245,240,0.95))]">
        <div class="space-y-5">
          <div
            class="inline-flex rounded-full border border-black/8 bg-white/80 px-3 py-1 text-xs font-semibold tracking-[0.18em] text-zinc-500 uppercase">
            Multi-user RAG
          </div>
          <div class="space-y-3">
            <h1
              class="max-w-lg text-4xl font-black tracking-tight text-heading">
              私有知识库隔离，公有知识库共享。
            </h1>
            <p class="max-w-xl text-sm leading-7 text-(--color-text-muted)">
              登录后，普通用户只能访问自己的私有知识库和全局公有知识库；管理员额外负责维护公有知识库。
            </p>
          </div>
          <div class="grid gap-3 sm:grid-cols-2">
            <div class="rounded-3xl border border-black/6 bg-white/78 p-4">
              <div
                class="text-xs font-semibold tracking-[0.14em] text-zinc-500 uppercase">
                模式
              </div>
              <div class="mt-2 text-lg font-bold text-heading">
                {{
                  features.private_knowledge_base_enabled
                    ? '公有 + 私有'
                    : '仅公有知识库'
                }}
              </div>
            </div>
            <div class="rounded-3xl border border-black/6 bg-white/78 p-4">
              <div
                class="text-xs font-semibold tracking-[0.14em] text-zinc-500 uppercase">
                注册
              </div>
              <div class="mt-2 text-lg font-bold text-heading">
                {{ features.open_registration_enabled ? '已开放' : '已关闭' }}
              </div>
            </div>
          </div>
        </div>
      </OCard>

      <OCard padding="lg" class="self-center">
        <div class="space-y-5">
          <div>
            <div
              class="text-sm font-semibold tracking-[0.18em] text-zinc-500 uppercase">
              {{ bootstrapLoading ? '加载配置中' : '访问工作台' }}
            </div>
            <h2 class="mt-2 text-2xl font-bold tracking-tight text-heading">
              {{ pageTitle }}
            </h2>
          </div>

          <div class="space-y-4">
            <OFormItem label="用户名" :required="true">
              <OInput
                v-model="form.username"
                :disabled="loading"
                placeholder="请输入用户名">
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
                @keydown.enter="submit">
                <template #prefix>
                  <LockOutlined class="text-zinc-400" />
                </template>
              </OInput>
            </OFormItem>
          </div>

          <div class="space-y-3">
            <OButton block :loading="loading" @click="submit">
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

          <p class="text-xs leading-6 text-(--color-text-muted)">
            普通用户账号需由管理员创建。默认管理员账号由后端自动初始化，请首次部署后尽快修改默认凭据。
          </p>
        </div>
      </OCard>
    </div>
  </div>
</template>
