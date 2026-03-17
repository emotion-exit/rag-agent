<script setup lang="ts">
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  MessageOutlined,
  BookOutlined,
  RobotOutlined,
  SettingOutlined
} from '@ant-design/icons-vue';
import { OConfigProvider } from '@/orange-ui';

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
    </div>
  </OConfigProvider>
</template>
