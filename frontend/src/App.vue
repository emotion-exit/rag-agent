<script setup lang="ts">
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  MessageOutlined,
  BookOutlined,
  RobotOutlined,
  SettingOutlined
} from '@ant-design/icons-vue';

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
</script>

<template>
  <div class="app-layout">
    <!-- Floating Minimalist Header -->
    <header class="app-header">
      <div class="header-content">
        <div class="logo-area">
          <div class="logo-icon-wrapper">
            <RobotOutlined class="logo-icon" />
          </div>
          <span class="logo-text">RAG.Agent</span>
        </div>
        <nav class="nav-menu">
          <router-link to="/" class="nav-item" active-class="nav-item-active">
            <MessageOutlined />
            智能问答
          </router-link>
          <router-link
            to="/knowledge-base"
            class="nav-item"
            active-class="nav-item-active">
            <BookOutlined />
            知识库
          </router-link>
          <router-link
            to="/settings"
            class="nav-item"
            active-class="nav-item-active">
            <SettingOutlined />
            设置
          </router-link>
        </nav>
      </div>
    </header>

    <!-- Main Centered Content -->
    <main
      :class="[
        'app-main',
        isScrollableRoute ? 'app-main-scrollable' : '',
        usesOverlayHeader ? 'app-main-overlay' : 'app-main-aligned'
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
</template>

<style scoped>
.app-layout {
  height: 100vh;
  overflow: hidden;
  background: var(--color-background);
  color: var(--color-text);
  display: flex;
  flex-direction: column;
  align-items: stretch;
  font-family:
    'SF Pro Display',
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    Roboto,
    Helvetica,
    Arial,
    sans-serif;
}

.app-header {
  position: sticky;
  top: 24px;
  z-index: 100;
  width: 100%;
  max-width: 1320px;
  margin: 0 auto;
  padding: 0 20px;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(24px) saturate(200%);
  -webkit-backdrop-filter: blur(24px) saturate(200%);
  padding: 10px 14px 10px 20px;
  border-radius: 100px;
  box-shadow:
    0 4px 24px rgba(0, 0, 0, 0.04),
    0 1px 4px rgba(0, 0, 0, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon-wrapper {
  background: var(--color-heading);
  color: var(--color-surface);
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.logo-text {
  font-weight: 700;
  font-size: 16px;
  letter-spacing: -0.3px;
  color: var(--color-heading);
}

.nav-menu {
  display: flex;
  gap: 8px;
  background: var(--color-surface-muted);
  padding: 4px;
  border-radius: 100px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 100px;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-muted);
  text-decoration: none;
  transition: all 0.2s ease;
}

.nav-item:hover {
  color: var(--color-heading);
  background: rgba(255, 255, 255, 0.4);
}

.nav-item-active {
  background: var(--color-surface);
  color: var(--color-heading);
  box-shadow:
    0 4px 12px rgba(0, 0, 0, 0.06),
    0 1px 2px rgba(0, 0, 0, 0.04);
}

.app-main {
  width: 100%;
  max-width: 1320px;
  margin: 0 auto;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 24px 20px 40px;
  overflow: hidden;
}

.app-main-overlay {
  margin-top: -78px;
}

.app-main-aligned {
  padding-top: 10px;
}

.app-main-scrollable {
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-gutter: stable;
}

@media (max-width: 768px) {
  .app-header {
    top: 16px;
    padding: 0 14px;
  }

  .app-main {
    padding: 18px 14px 28px;
  }

  .app-main-overlay {
    margin-top: -72px;
  }

  .app-main-aligned {
    padding-top: 8px;
  }
}

@media (max-width: 640px) {
  .header-content {
    flex-direction: column;
    align-items: stretch;
    border-radius: 24px;
  }

  .nav-menu {
    width: 100%;
  }

  .nav-item {
    flex: 1;
    justify-content: center;
  }
}
</style>
