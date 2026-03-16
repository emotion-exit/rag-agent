<script setup lang="ts">
import { computed } from 'vue';
import {
  CheckCircleOutlined,
  CloseOutlined,
  LoadingOutlined,
  WarningOutlined
} from '@ant-design/icons-vue';
import type { KnowledgeBaseJobStatus } from '@/types/knowledgeBase';

defineOptions({
  name: 'KnowledgeBaseTaskProgressModal'
});

const props = defineProps<{
  visible: boolean;
  task: KnowledgeBaseJobStatus | null;
}>();

const emit = defineEmits<{
  close: [];
}>();

const isRunning = computed(
  () => props.task?.status === 'queued' || props.task?.status === 'running'
);
const statusLabel = computed(() => {
  if (!props.task) return '未开始';
  if (props.task.status === 'queued') return '排队中';
  if (props.task.status === 'running') return '执行中';
  if (props.task.status === 'completed') return '已完成';
  return '失败';
});
const title = computed(() => {
  if (!props.task) return '知识库任务';
  return props.task.job_type === 'upload' ? '上传任务进度' : '迁移任务进度';
});
const progressPercent = computed(() => {
  if (!props.task) return 0;
  const total = Number(props.task.total_documents || 0);
  const processed = Number(props.task.processed_documents || 0);
  if (total <= 0) return props.task.status === 'completed' ? 100 : 0;
  return Math.min(100, Math.round((processed / total) * 100));
});
const chunkProgressText = computed(() => {
  if (!props.task) return '';
  if (props.task.total_chunks > 0) {
    return `${props.task.processed_chunks} / ${props.task.total_chunks} 个分块`;
  }
  if (props.task.processed_chunks > 0) {
    return `已处理 ${props.task.processed_chunks} 个分块`;
  }
  return '等待分块统计';
});

function requestClose() {
  if (isRunning.value) return;
  emit('close');
}
</script>

<template>
  <Teleport to="body">
    <Transition name="kb-modal-fade">
      <div v-if="visible && task" class="kb-modal-backdrop">
        <div class="kb-modal-panel kb-task-panel">
          <div class="kb-modal-head">
            <div>
              <div class="kb-modal-title">{{ title }}</div>
              <div class="kb-modal-subtitle">{{ task.message }}</div>
            </div>
            <button
              type="button"
              class="kb-modal-close"
              :disabled="isRunning"
              @click="requestClose">
              <CloseOutlined />
            </button>
          </div>

          <div :class="['kb-task-status', `kb-task-status-${task.status}`]">
            <LoadingOutlined v-if="isRunning" class="spin" />
            <CheckCircleOutlined v-else-if="task.status === 'completed'" />
            <WarningOutlined v-else />
            <span>{{ statusLabel }}</span>
          </div>

          <div class="kb-task-progress-block">
            <div class="kb-task-progress-head">
              <span>文档进度</span>
              <span>
                {{ task.processed_documents }} / {{ task.total_documents }}
              </span>
            </div>
            <div class="kb-task-progress-track">
              <div
                class="kb-task-progress-fill"
                :style="{ width: `${progressPercent}%` }" />
            </div>
          </div>

          <div class="kb-task-stats">
            <div class="kb-task-stat">
              <span class="kb-task-stat-label">分块进度</span>
              <strong class="kb-task-stat-value">
                {{ chunkProgressText }}
              </strong>
            </div>
            <div class="kb-task-stat">
              <span class="kb-task-stat-label">当前文件</span>
              <strong class="kb-task-stat-value kb-task-current">
                {{ task.current_document || '等待开始' }}
              </strong>
            </div>
          </div>

          <div v-if="task.error_message" class="kb-task-error">
            {{ task.error_message }}
          </div>

          <div class="kb-task-tip">
            {{
              isRunning
                ? '任务正在后台执行，请保持当前窗口打开。'
                : '任务已经结束，可以关闭此窗口。'
            }}
          </div>

          <div class="kb-modal-actions">
            <button
              type="button"
              class="kb-btn kb-btn-secondary"
              :disabled="isRunning"
              @click="requestClose">
              关闭
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
  width: min(680px, 100%);
  max-height: min(88vh, 920px);
  overflow: auto;
  padding: 32px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(40px) saturate(200%);
  -webkit-backdrop-filter: blur(40px) saturate(200%);
  border: 1px solid rgba(255, 255, 255, 0.8);
  box-shadow:
    0 20px 48px rgba(0, 0, 0, 0.1),
    0 8px 24px rgba(0, 0, 0, 0.05);
}

.kb-modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.kb-modal-title {
  color: var(--color-heading);
  font-size: 20px;
  font-weight: 700;
}

.kb-modal-subtitle,
.kb-task-tip {
  margin-top: 6px;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.kb-modal-close {
  width: 38px;
  height: 38px;
  border: 1px solid var(--color-border-soft);
  border-radius: 50%;
  background: var(--color-surface);
  color: var(--color-text-secondary);
  cursor: pointer;
}

.kb-modal-close:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.kb-task-status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 0 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
}

.kb-task-status-queued,
.kb-task-status-running {
  background: var(--color-warning-soft);
  color: var(--color-warning-strong);
}

.kb-task-status-completed {
  background: var(--color-success-soft);
  color: var(--color-success-strong);
}

.kb-task-status-failed {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}

.kb-task-progress-block {
  margin-top: 18px;
}

.kb-task-progress-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.kb-task-progress-track {
  margin-top: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--color-surface-soft);
  overflow: hidden;
}

.kb-task-progress-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    var(--color-success) 0%,
    var(--color-success-strong) 100%
  );
  transition: width 0.3s ease;
}

.kb-task-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.kb-task-stat {
  padding: 14px 16px;
  border-radius: 18px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
}

.kb-task-stat-label {
  color: var(--color-text-muted);
  font-size: 12px;
}

.kb-task-stat-value {
  display: block;
  margin-top: 6px;
  color: var(--color-heading);
  font-size: 16px;
  font-weight: 700;
}

.kb-task-current {
  font-size: 14px;
  line-height: 1.5;
}

.kb-task-error {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 16px;
  background: var(--color-danger-soft);
  border: 1px solid var(--color-danger-border);
  color: var(--color-danger);
  font-size: 13px;
  line-height: 1.6;
}

.kb-modal-actions {
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
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

.kb-btn:disabled {
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

.kb-btn-secondary:not(:disabled):active {
  transform: scale(0.98);
}

.kb-modal-fade-enter-active,
.kb-modal-fade-leave-active {
  transition: opacity 0.22s ease;
}

.kb-modal-fade-enter-from,
.kb-modal-fade-leave-to {
  opacity: 0;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 720px) {
  .kb-modal-backdrop {
    padding: 14px;
  }

  .kb-modal-panel {
    padding: 18px;
    border-radius: 24px;
  }

  .kb-task-stats {
    grid-template-columns: minmax(0, 1fr);
  }

  .kb-btn {
    width: 100%;
  }
}
</style>
