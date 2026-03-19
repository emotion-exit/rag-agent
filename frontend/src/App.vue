<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  MessageOutlined,
  BookOutlined,
  RobotOutlined,
  LoadingOutlined,
  SettingOutlined
} from '@ant-design/icons-vue';
import { OButton, OConfigProvider } from '@/orange-ui';
import { isDesktopApp } from '@/services/runtime';

const route = useRoute();
const router = useRouter();
const isScrollableRoute = computed(
  () => route.name === 'knowledge-base' || route.name === 'settings'
);
const usesOverlayHeader = computed(() => route.name === 'chat');
const keepAliveIncludes = computed(() =>
  router
    .getRoutes()
    .map((item) => item.meta.keepAliveName)
    .filter(
      (item): item is string => typeof item === 'string' && item.length > 0
    )
);
const desktopMode = isDesktopApp();
const desktopBackendState = ref<'idle' | 'starting' | 'ready' | 'error'>(
  desktopMode ? 'starting' : 'ready'
);
const desktopBackendError = ref('');
let desktopBackendPollTimer: number | null = null;

const showDesktopStartupOverlay = computed(
  () => desktopMode && desktopBackendState.value !== 'ready'
);
const desktopStartupTitle = computed(() => {
  if (desktopBackendState.value === 'error') {
    return '本地服务启动失败';
  }

  return '服务启动中';
});
const desktopStartupDescription = computed(() => {
  if (desktopBackendState.value === 'error') {
    return (
      desktopBackendError.value ||
      '内置服务没有正常启动，请检查模型配置或端口占用。'
    );
  }

  return '应用界面已打开，正在等待服务完成启动。';
});

async function refreshDesktopBackendStatus() {
  if (!window.desktopApp) {
    desktopBackendState.value = 'ready';
    desktopBackendError.value = '';
    return;
  }

  try {
    const status = await window.desktopApp.getBackendStatus();
    desktopBackendState.value = status.ready ? 'ready' : status.state || 'idle';
    desktopBackendError.value = status.errorMessage || '';

    if (status.ready && desktopBackendPollTimer !== null) {
      window.clearInterval(desktopBackendPollTimer);
      desktopBackendPollTimer = null;
    }
  } catch {
    desktopBackendState.value = 'error';
    desktopBackendError.value = '无法获取内置服务状态，请稍后重试。';
  }
}

async function restartDesktopBackend() {
  if (!window.desktopApp) {
    return;
  }

  desktopBackendState.value = 'starting';
  desktopBackendError.value = '';

  try {
    await window.desktopApp.restartBackend();
  } catch {
    // The actual failure reason is polled from the main process state.
  }

  await refreshDesktopBackendStatus();
}

function openSettings() {
  router.push({ name: 'settings' });
}

onMounted(async () => {
  if (!desktopMode) {
    return;
  }

  await refreshDesktopBackendStatus();

  if (desktopBackendState.value !== 'ready') {
    desktopBackendPollTimer = window.setInterval(() => {
      void refreshDesktopBackendStatus();
    }, 800);
  }
});

onBeforeUnmount(() => {
  if (desktopBackendPollTimer !== null) {
    window.clearInterval(desktopBackendPollTimer);
    desktopBackendPollTimer = null;
  }
});

const appTheme = {
  colorPrimary: '#18181b',
  colorPrimaryStrong: '#09090b',
  colorPrimarySoft: '#f4f4f5'
};
</script>

<template>
  <OConfigProvider :theme="appTheme">
    <div
      class="flex h-screen flex-col items-center overflow-hidden bg-(--color-background) text-(--color-text)">
      <header
        class="sticky top-6 z-100 w-full max-w-6xl px-6 max-md:top-4 max-md:px-4">
        <div
          class="flex items-center justify-between rounded-full border border-white/30 bg-white/90 px-5 py-2.5 shadow-[0_4px_24px_rgba(24,24,27,0.08)] backdrop-blur-2xl backdrop-saturate-200 max-sm:flex-col max-sm:items-stretch max-sm:rounded-3xl max-sm:px-4">
          <div class="flex items-center gap-3">
            <div
              class="flex h-8 w-8 items-center justify-center rounded-full bg-(--color-heading) text-(--color-surface) text-sm shadow-sm">
              <RobotOutlined />
            </div>
            <span
              class="text-base font-bold tracking-tight text-(--color-heading)">
              RAG.Agent
            </span>
          </div>
          <nav
            class="flex gap-1 rounded-full bg-(--color-surface-muted) p-1 max-sm:mt-2.5 max-sm:w-full">
            <router-link
              to="/"
              class="flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium text-(--color-text-muted) transition-all duration-200 hover:bg-white/50 hover:text-(--color-heading) max-sm:flex-1 max-sm:justify-center"
              active-class="bg-(--color-surface) text-(--color-heading) shadow-[0_2px_8px_rgba(24,24,27,0.08)]">
              <MessageOutlined />
              智能问答
            </router-link>
            <router-link
              to="/knowledge-base"
              class="flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium text-(--color-text-muted) transition-all duration-200 hover:bg-white/50 hover:text-(--color-heading) max-sm:flex-1 max-sm:justify-center"
              active-class="bg-(--color-surface) text-(--color-heading) shadow-[0_2px_8px_rgba(24,24,27,0.08)]">
              <BookOutlined />
              知识库
            </router-link>
            <router-link
              to="/settings"
              class="flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium text-(--color-text-muted) transition-all duration-200 hover:bg-white/50 hover:text-(--color-heading) max-sm:flex-1 max-sm:justify-center"
              active-class="bg-(--color-surface) text-(--color-heading) shadow-[0_2px_8px_rgba(24,24,27,0.08)]">
              <SettingOutlined />
              设置
            </router-link>
          </nav>
        </div>
      </header>

      <main
        :class="[
          'flex w-full max-w-6xl flex-1 flex-col overflow-hidden px-6 pb-8 pt-5 max-md:px-4 max-md:pb-6 max-md:pt-4',
          usesOverlayHeader ? '-mt-19.5 max-md:-mt-18' : 'pt-2.5 max-md:pt-2',
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

      <transition name="fade">
        <div
          v-if="showDesktopStartupOverlay"
          class="absolute inset-0 z-200 flex items-center justify-center bg-[rgba(244,244,245,0.82)] px-6 backdrop-blur-xl">
          <div
            class="w-full max-w-md rounded-[28px] border border-white/70 bg-white/92 p-7 shadow-[0_24px_80px_rgba(24,24,27,0.16)]">
            <div class="flex items-start gap-4">
              <div
                class="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-zinc-900 text-white shadow-sm">
                <LoadingOutlined
                  v-if="desktopBackendState !== 'error'"
                  class="animate-spin text-lg" />
                <RobotOutlined v-else class="text-lg" />
              </div>
              <div class="min-w-0 flex-1">
                <div
                  class="text-lg font-semibold tracking-tight text-(--color-heading)">
                  {{ desktopStartupTitle }}
                </div>
                <p class="mt-2 text-sm leading-7 text-(--color-text-muted)">
                  {{ desktopStartupDescription }}
                </p>
              </div>
            </div>

            <div class="mt-5 flex flex-wrap gap-2.5">
              <OButton
                v-if="desktopBackendState === 'error'"
                size="sm"
                @click="restartDesktopBackend">
                重试启动
              </OButton>
              <OButton
                v-if="desktopBackendState === 'error'"
                variant="secondary"
                size="sm"
                @click="openSettings">
                打开设置
              </OButton>
              <div
                v-else
                class="inline-flex items-center gap-2 rounded-full bg-zinc-100 px-3 py-1.5 text-xs font-medium text-zinc-600">
                <span class="h-1.5 w-1.5 rounded-full bg-zinc-500"></span>
                服务启动中
              </div>
            </div>
          </div>
        </div>
      </transition>
    </div>
  </OConfigProvider>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
