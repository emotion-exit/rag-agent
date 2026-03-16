<script setup lang="ts">
import { CloseOutlined, WarningOutlined } from '@ant-design/icons-vue';

defineOptions({
  name: 'KnowledgeDangerConfirmModal'
});

const props = withDefaults(
  defineProps<{
    visible: boolean;
    title: string;
    message: string;
    impactItems?: string[];
    impactStats?: Array<{ label: string; value: string }>;
    confirmText?: string;
    cancelText?: string;
    submitting?: boolean;
  }>(),
  {
    impactItems: () => [],
    impactStats: () => [],
    confirmText: '确认操作',
    cancelText: '取消',
    submitting: false
  }
);

const emit = defineEmits<{
  close: [];
  confirm: [];
}>();

function requestClose() {
  if (props.submitting) return;
  emit('close');
}

function requestConfirm() {
  if (props.submitting) return;
  emit('confirm');
}
</script>

<template>
  <Teleport to="body">
    <Transition name="kb-modal-fade">
      <div v-if="visible" class="kb-modal-backdrop">
        <div class="kb-modal-panel kb-danger-panel">
          <div class="kb-modal-head">
            <div class="kb-danger-intro">
              <div class="kb-danger-icon">
                <WarningOutlined />
              </div>
              <div>
                <div class="kb-modal-title">{{ title }}</div>
                <div class="kb-modal-subtitle">{{ message }}</div>
              </div>
            </div>
            <button
              type="button"
              class="kb-modal-close"
              :disabled="submitting"
              @click="requestClose">
              <CloseOutlined />
            </button>
          </div>

          <div v-if="impactStats.length > 0" class="kb-danger-stats-grid">
            <div
              v-for="item in impactStats"
              :key="item.label"
              class="kb-danger-stat-card">
              <div class="kb-danger-stat-value">{{ item.value }}</div>
              <div class="kb-danger-stat-label">{{ item.label }}</div>
            </div>
          </div>

          <div v-if="impactItems.length > 0" class="kb-danger-card">
            <div class="kb-danger-card-title">此操作会同时影响</div>
            <ul class="kb-danger-list">
              <li v-for="item in impactItems" :key="item">{{ item }}</li>
            </ul>
          </div>

          <div class="kb-modal-actions">
            <button
              type="button"
              class="kb-btn kb-btn-secondary"
              :disabled="submitting"
              @click="requestClose">
              {{ cancelText }}
            </button>
            <button
              type="button"
              class="kb-btn kb-btn-danger"
              :disabled="submitting"
              @click="requestConfirm">
              {{ submitting ? '处理中...' : confirmText }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.kb-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.kb-modal-panel {
  width: min(560px, 100%);
  max-height: min(88vh, 920px);
  overflow: auto;
  padding: 28px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(40px) saturate(200%);
  -webkit-backdrop-filter: blur(40px) saturate(200%);
  border: 1px solid rgba(255, 255, 255, 0.8);
  box-shadow:
    0 20px 48px rgba(0, 0, 0, 0.1),
    0 8px 24px rgba(0, 0, 0, 0.05);
}

.kb-danger-panel {
  width: min(540px, 100%);
}

.kb-modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.kb-danger-intro {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}

.kb-danger-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: rgba(177, 55, 42, 0.12);
  color: #9e3328;
  font-size: 18px;
  flex-shrink: 0;
}

.kb-modal-title {
  color: var(--color-heading);
  font-size: 20px;
  font-weight: 700;
}

.kb-modal-subtitle {
  margin-top: 6px;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.7;
}

.kb-modal-close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.04);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.kb-modal-close:hover {
  background: rgba(0, 0, 0, 0.08);
  color: var(--color-heading);
}

.kb-danger-card {
  margin-top: 18px;
  padding: 16px 18px;
  border-radius: 18px;
  background: rgba(177, 55, 42, 0.06);
  border: 1px solid rgba(177, 55, 42, 0.12);
}

.kb-danger-stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 10px;
  margin-top: 18px;
}

.kb-danger-stat-card {
  padding: 14px 14px 12px;
  border-radius: 18px;
  background: rgba(177, 55, 42, 0.05);
  border: 1px solid rgba(177, 55, 42, 0.1);
}

.kb-danger-stat-value {
  color: #9e3328;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.2;
}

.kb-danger-stat-label {
  margin-top: 6px;
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.kb-danger-card-title {
  color: #9e3328;
  font-size: 13px;
  font-weight: 700;
}

.kb-danger-list {
  margin: 10px 0 0;
  padding-left: 18px;
  color: #52525b;
  font-size: 13px;
  line-height: 1.7;
}

.kb-modal-actions {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.kb-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 20px;
  border: none;
  border-radius: 999px;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.kb-btn:disabled,
.kb-modal-close:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.kb-btn-secondary {
  background: rgba(0, 0, 0, 0.04);
  color: var(--color-text);
}

.kb-btn-secondary:not(:disabled):hover {
  background: rgba(0, 0, 0, 0.08);
}

.kb-btn-danger {
  background: rgba(177, 55, 42, 0.1);
  color: #9e3328;
}

.kb-btn-danger:not(:disabled):hover {
  background: rgba(177, 55, 42, 0.16);
}

.kb-modal-fade-enter-active,
.kb-modal-fade-leave-active {
  transition: opacity 0.22s ease;
}

.kb-modal-fade-enter-from,
.kb-modal-fade-leave-to {
  opacity: 0;
}

@media (max-width: 720px) {
  .kb-modal-backdrop {
    padding: 14px;
  }

  .kb-modal-panel {
    padding: 18px;
    border-radius: 24px;
  }

  .kb-modal-actions {
    flex-direction: column-reverse;
  }

  .kb-btn {
    width: 100%;
  }
}
</style>
