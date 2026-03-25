<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  MessageOutlined,
  BookOutlined,
  RobotOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined
} from '@ant-design/icons-vue';
import { OConfigProvider } from '@/orange-ui';
import { getApiBase } from '@/services/runtime';
import {
  clearAuthSession,
  refreshAuthSession,
  useAuthState
} from '@/services/auth';

const route = useRoute();
const router = useRouter();
const authState = useAuthState();
const isScrollableRoute = computed(
  () => route.name === 'knowledge-base' || route.name === 'settings'
);
const usesOverlayHeader = computed(() => route.name === 'chat');
const isLoginRoute = computed(() => route.name === 'login');
const keepAliveIncludes = computed(() =>
  router
    .getRoutes()
    .map((item) => item.meta.keepAliveName)
    .filter(
      (item): item is string => typeof item === 'string' && item.length > 0
    )
);

const appTheme = {
  colorPrimary: '#18181b',
  colorPrimaryStrong: '#09090b',
  colorPrimarySoft: '#f4f4f5'
};

async function handleLogout() {
  const token = authState.session?.token;
  try {
    if (token) {
      await fetch(`${getApiBase()}/api/auth/logout`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
    }
  } catch {
    // noop
  } finally {
    clearAuthSession();
    await router.replace({ name: 'login' });
  }
}

onMounted(() => {
  void (async () => {
    const session = await refreshAuthSession();
    if (!session && route.name !== 'login') {
      await router.replace({ name: 'login' });
    }
  })();
});
</script>

<template>
  <OConfigProvider :theme="appTheme">
    <div
      class="flex h-screen flex-col items-center overflow-hidden bg-(--color-background) text-(--color-text)">
      <header
        v-if="!isLoginRoute"
        class="sticky top-6 z-100 w-full max-w-6xl px-6 max-md:top-4 max-md:px-4">
        <div
          class="flex items-center justify-between rounded-full border border-white/30 bg-white/90 px-5 py-2.5 shadow-[0_4px_24px_rgba(24,24,27,0.08)] backdrop-blur-2xl backdrop-saturate-200 max-sm:flex-col max-sm:items-stretch max-sm:rounded-3xl max-sm:px-4">
          <div class="flex items-center gap-3">
            <div
              class="flex h-8 w-8 items-center justify-center rounded-full bg-heading text-surface text-sm shadow-sm">
              <RobotOutlined />
            </div>
            <span class="text-base font-bold tracking-tight text-heading">
              RAG.Agent
            </span>
          </div>
          <nav
            class="flex gap-1 rounded-full bg-surface-muted p-1 max-sm:mt-2.5 max-sm:w-full">
            <router-link
              to="/"
              class="flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium text-(--color-text-muted) transition-all duration-200 hover:bg-white/50 hover:text-heading max-sm:flex-1 max-sm:justify-center"
              active-class="bg-(--color-surface) text-heading shadow-[0_2px_8px_rgba(24,24,27,0.08)]">
              <MessageOutlined />
              智能问答
            </router-link>
            <router-link
              to="/knowledge-base"
              class="flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium text-(--color-text-muted) transition-all duration-200 hover:bg-white/50 hover:text-heading max-sm:flex-1 max-sm:justify-center"
              active-class="bg-(--color-surface) text-heading shadow-[0_2px_8px_rgba(24,24,27,0.08)]">
              <BookOutlined />
              知识库
            </router-link>
            <router-link
              to="/settings"
              class="flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium text-(--color-text-muted) transition-all duration-200 hover:bg-white/50 hover:text-heading max-sm:flex-1 max-sm:justify-center"
              active-class="bg-(--color-surface) text-heading shadow-[0_2px_8px_rgba(24,24,27,0.08)]">
              <SettingOutlined />
              设置
            </router-link>
          </nav>
          <div class="flex items-center gap-2 max-sm:mt-2.5 max-sm:justify-end">
            <div
              class="inline-flex items-center gap-2 rounded-full border border-black/8 bg-white/80 px-3 py-1.5 text-sm text-heading">
              <UserOutlined class="text-xs text-zinc-500" />
              <span>{{ authState.session?.user.username || '未登录' }}</span>
              <span class="text-xs text-zinc-400">
                {{
                  authState.session?.user.role === 'admin' ? '管理员' : '用户'
                }}
              </span>
            </div>
            <button
              type="button"
              class="inline-flex h-10 w-10 items-center justify-center rounded-full text-zinc-500 transition hover:bg-black/5 hover:text-heading"
              @click="handleLogout">
              <LogoutOutlined />
            </button>
          </div>
        </div>
      </header>

      <main
        :class="[
          'flex w-full max-w-6xl flex-1 flex-col overflow-hidden px-6 pb-8 pt-5 max-md:px-4 max-md:pb-6 max-md:pt-4',
          isLoginRoute
            ? 'pt-2.5 max-md:pt-2'
            : usesOverlayHeader
              ? '-mt-19.5 max-md:-mt-18'
              : 'pt-2.5 max-md:pt-2',
          isScrollableRoute
            ? 'o-page-scroll overflow-y-auto overflow-x-hidden'
            : ''
        ]">
        <RouterView v-slot="{ Component, route: currentRoute }">
          <KeepAlive :include="keepAliveIncludes">
            <component
              :is="Component"
              v-if="currentRoute.meta.keepAlive"
              :key="String(currentRoute.name ?? currentRoute.path)" />
          </KeepAlive>
          <component
            :is="Component"
            v-if="!currentRoute.meta.keepAlive"
            :key="String(currentRoute.name ?? currentRoute.path)" />
        </RouterView>
      </main>
    </div>
  </OConfigProvider>
</template>
