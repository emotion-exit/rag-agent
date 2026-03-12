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
  background-color: #fafafa;
  color: #1a1a1a;
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
  max-width: 900px;
  margin: 0 auto;
  padding: 0 20px;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  padding: 12px 16px 12px 20px;
  border-radius: 100px;
  box-shadow:
    0 4px 24px -8px rgba(0, 0, 0, 0.05),
    0 1px 3px rgba(0, 0, 0, 0.02);
  border: 1px solid rgba(0, 0, 0, 0.04);
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon-wrapper {
  background: #1a1a1a;
  color: #fff;
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
  color: #1a1a1a;
}

.nav-menu {
  display: flex;
  gap: 8px;
  background: #f4f4f5;
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
  color: #71717a;
  text-decoration: none;
  transition: all 0.2s ease;
}

.nav-item:hover {
  color: #1a1a1a;
}

.nav-item-active {
  background: #ffffff;
  color: #1a1a1a;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.app-main {
  width: 100%;
  max-width: 900px;
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
</style>
