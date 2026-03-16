<script setup lang="ts">
import { computed } from 'vue';
import {
  CheckCircleOutlined,
  LoadingOutlined,
  WarningOutlined
} from '@ant-design/icons-vue';
import type { KnowledgeBaseJobStatus } from '@/types/knowledgeBase';
import { OButton, OCard, OModal } from '@/orange-ui';

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
  <OModal
    v-if="visible && task"
    :visible="visible && !!task"
    :title="title"
    :subtitle="task.message"
    :closable="!isRunning"
    width="min(680px, 100%)"
    @close="requestClose">
    <div class="space-y-4.5">
      <div
        :class="[
          'inline-flex min-h-9 items-center gap-2 rounded-full px-3.5 text-[13px] font-bold',
          task.status === 'queued' || task.status === 'running'
            ? 'bg-(--oui-color-warning-soft) text-(--oui-color-warning)'
            : task.status === 'completed'
              ? 'bg-(--oui-color-success-soft) text-(--oui-color-success)'
              : 'bg-(--oui-color-danger-soft) text-(--oui-color-danger)'
        ]">
        <LoadingOutlined v-if="isRunning" class="spin" />
        <CheckCircleOutlined v-else-if="task.status === 'completed'" />
        <WarningOutlined v-else />
        <span>{{ statusLabel }}</span>
      </div>

      <div>
        <div
          class="flex items-center justify-between text-[13px] font-semibold text-(--oui-color-text-secondary)">
          <span>文档进度</span>
          <span>
            {{ task.processed_documents }} / {{ task.total_documents }}
          </span>
        </div>
        <div
          class="mt-2.5 h-2.5 overflow-hidden rounded-full bg-(--oui-color-surface-soft)">
          <div
            class="h-full rounded-full bg-(--oui-color-primary) transition-[width] duration-300"
            :style="{ width: `${progressPercent}%` }" />
        </div>
      </div>

      <div class="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        <OCard padding="sm">
          <div class="text-xs text-(--oui-color-text-muted)">分块进度</div>
          <div
            class="mt-1.5 text-sm font-semibold leading-6 text-(--oui-color-heading)">
            {{ chunkProgressText }}
          </div>
        </OCard>
        <OCard padding="sm">
          <div class="text-xs text-(--oui-color-text-muted)">当前文件</div>
          <div
            class="mt-1.5 truncate text-sm font-semibold leading-6 text-(--oui-color-heading)">
            {{ task.current_document || '等待开始' }}
          </div>
        </OCard>
      </div>

      <OCard v-if="task.error_message" tone="danger" padding="sm">
        <div class="text-sm leading-6 text-(--oui-color-danger)">
          {{ task.error_message }}
        </div>
      </OCard>

      <div class="text-[13px] leading-6 text-(--oui-color-text-muted)">
        {{
          isRunning
            ? '任务正在后台执行，请保持当前窗口打开。'
            : '任务已经结束，可以关闭此窗口。'
        }}
      </div>
    </div>

    <template #footer>
      <OButton variant="secondary" :disabled="isRunning" @click="requestClose">
        关闭
      </OButton>
    </template>
  </OModal>
</template>
