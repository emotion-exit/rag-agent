<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  MessageOutlined,
  BookOutlined,
  RobotOutlined,
} from '@ant-design/icons-vue'

const route = useRoute()
const selectedKeys = computed(() => {
  if (route.path === '/knowledge-base') return ['knowledge-base']
  return ['chat']
})
</script>

<template>
  <a-layout style="min-height: 100vh">
    <a-layout-sider
      width="220"
      theme="dark"
      style="position: fixed; height: 100vh; left: 0; top: 0; bottom: 0; overflow: auto; z-index: 10"
    >
      <div class="logo-area">
        <RobotOutlined class="logo-icon" />
        <span class="logo-text">RAG Agent</span>
      </div>
      <a-menu
        theme="dark"
        mode="inline"
        :selected-keys="selectedKeys"
      >
        <a-menu-item key="chat">
          <router-link to="/">
            <MessageOutlined />
            <span>智能问答</span>
          </router-link>
        </a-menu-item>
        <a-menu-item key="knowledge-base">
          <router-link to="/knowledge-base">
            <BookOutlined />
            <span>知识库管理</span>
          </router-link>
        </a-menu-item>
      </a-menu>
    </a-layout-sider>

    <a-layout style="margin-left: 220px">
      <a-layout-content style="padding: 24px; min-height: 100vh; background: #f0f2f5">
        <RouterView />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<style scoped>
.logo-area {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  margin-bottom: 4px;
}

.logo-icon {
  font-size: 24px;
  color: #1890ff;
}

.logo-text {
  color: #fff;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0.5px;
}
</style>
