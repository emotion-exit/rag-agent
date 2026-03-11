<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import {
  MessageOutlined,
  BookOutlined,
  RobotOutlined
} from '@ant-design/icons-vue';

const route = useRoute();
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
        </nav>
      </div>
    </header>

    <!-- Main Centered Content -->
    <main class="app-main">
      <RouterView />
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
  align-items: center;
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
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 24px 20px 40px;
  margin-top: -78px;
  overflow: hidden;
}
</style>
