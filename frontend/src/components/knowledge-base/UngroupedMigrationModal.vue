<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import {
  CloseOutlined,
  LoadingOutlined,
  WarningOutlined
} from '@ant-design/icons-vue';
import type { DocumentInfo, KnowledgeSpace } from '@/types/knowledgeBase';

defineOptions({
  name: 'UngroupedMigrationModal'
});

const props = defineProps<{
  visible: boolean;
  submitting: boolean;
  spaces: KnowledgeSpace[];
  ungroupedDocuments: DocumentInfo[];
}>();

const emit = defineEmits<{
  close: [];
  submit: [targetSpaceId: string];
}>();

const targetSpaceId = ref('');
const localWarning = ref('');

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return;
    targetSpaceId.value = '';
    localWarning.value = '';
  }
);

const previewDocuments = computed(() => props.ungroupedDocuments.slice(0, 5));
const hiddenCount = computed(() =>
  Math.max(props.ungroupedDocuments.length - previewDocuments.value.length, 0)
);
const estimatedChunkCount = computed(() =>
  props.ungroupedDocuments.reduce(
    (total, doc) => total + Number(doc.chunk_count || 0),
    0
  )
);
const selectedSpace = computed(
  () =>
    props.spaces.find((item) => item.space_id === targetSpaceId.value) || null
);

function requestClose() {
  if (props.submitting) return;
  emit('close');
}

function submitMigration() {
  if (!targetSpaceId.value) {
    localWarning.value = '请先选择迁移目标知识空间。';
    return;
  }

  emit('submit', targetSpaceId.value);
}
</script>

<template>
  <Teleport to="body">
    <Transition name="kb-modal-fade">
      <div v-if="visible" class="kb-modal-backdrop" @click.self="requestClose">
        <div class="kb-modal-panel kb-migration-panel">
          <div class="kb-modal-head">
            <div>
              <div class="kb-modal-title">迁移未归类文档</div>
              <div class="kb-modal-subtitle">
                将历史未归类文档统一迁移到正式知识空间，并重建对应索引。
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

          <div class="kb-warning-card">
            <WarningOutlined class="kb-warning-icon" />
            <div class="kb-warning-copy">
              <div class="kb-warning-title">此操作会重新 embedding</div>
              <div class="kb-warning-text">
                系统会把目标空间的分类、主题、标签和路径重新写入文档，并为受影响文本块重新建立向量索引。迁移期间这些文档会短暂重建检索结果。
              </div>
            </div>
          </div>

          <div class="kb-migration-stats">
            <div class="kb-migration-stat">
              <span class="kb-migration-label">待迁移文档</span>
              <strong class="kb-migration-value">
                {{ ungroupedDocuments.length }} 篇
              </strong>
            </div>
            <div class="kb-migration-stat">
              <span class="kb-migration-label">预计重建分块</span>
              <strong class="kb-migration-value">
                {{ estimatedChunkCount }} 个
              </strong>
              <div class="kb-migration-hint">
                基于当前分块数预估，实际重建后可能略有变化
              </div>
            </div>
            <div class="kb-migration-stat">
              <span class="kb-migration-label">目标空间</span>
              <strong class="kb-migration-value kb-migration-space">
                {{ selectedSpace ? selectedSpace.path : '尚未选择' }}
              </strong>
            </div>
          </div>

          <label class="kb-field-block">
            <span class="kb-field-label">迁移到</span>
            <select
              v-model="targetSpaceId"
              class="kb-field-input kb-field-select"
              :disabled="submitting || spaces.length === 0">
              <option value="">请选择目标知识空间</option>
              <option
                v-for="space in spaces"
                :key="space.space_id"
                :value="space.space_id">
                {{ space.path }}
              </option>
            </select>
          </label>

          <div class="kb-preview-list">
            <div class="kb-preview-head">本次会处理的文档</div>
            <div class="kb-preview-items">
              <div
                v-for="doc in previewDocuments"
                :key="doc.doc_id"
                class="kb-preview-item">
                <div class="kb-preview-name">{{ doc.filename }}</div>
                <div class="kb-preview-meta">{{ doc.chunk_count }} 个分块</div>
              </div>
              <div v-if="hiddenCount > 0" class="kb-preview-more">
                其余 {{ hiddenCount }} 篇文档也会一起迁移
              </div>
            </div>
          </div>

          <div v-if="localWarning" class="kb-warning-inline">
            {{ localWarning }}
          </div>

          <div class="kb-modal-actions">
            <button
              type="button"
              class="kb-btn kb-btn-secondary"
              :disabled="submitting"
              @click="requestClose">
              取消
            </button>
            <button
              type="button"
              class="kb-btn kb-btn-danger"
              :disabled="submitting || !targetSpaceId"
              @click="submitMigration">
              <LoadingOutlined v-if="submitting" class="spin" />
              <WarningOutlined v-else />
              开始迁移并重建索引
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
  z-index: 180;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(24, 24, 27, 0.16);
  backdrop-filter: blur(8px);
}

.kb-modal-panel {
  width: min(760px, 100%);
  max-height: min(88vh, 920px);
  overflow: auto;
  padding: 24px;
  border-radius: 28px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-floating);
}

.kb-migration-panel {
  width: min(720px, 100%);
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

.kb-modal-subtitle {
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

.kb-warning-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  padding: 14px 16px;
  border-radius: 18px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
}

.kb-warning-icon {
  margin-top: 2px;
  color: var(--color-warning);
}

.kb-warning-title {
  color: var(--color-warning-strong);
  font-size: 14px;
  font-weight: 700;
}

.kb-warning-text,
.kb-preview-meta,
.kb-migration-hint {
  margin-top: 4px;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.kb-migration-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.kb-migration-stat {
  padding: 14px 16px;
  border-radius: 18px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
}

.kb-migration-label {
  color: var(--color-text-muted);
  font-size: 12px;
}

.kb-migration-value {
  display: block;
  margin-top: 6px;
  color: var(--color-heading);
  font-size: 18px;
  font-weight: 700;
}

.kb-migration-space {
  font-size: 14px;
  line-height: 1.5;
}

.kb-field-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 18px;
}

.kb-field-label {
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.kb-field-input {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: 16px;
  background: var(--color-surface);
  color: var(--color-text);
  padding: 12px 14px;
  font: inherit;
}

.kb-field-input:focus {
  outline: none;
  border-color: var(--color-warning);
  box-shadow: 0 0 0 3px rgba(217, 119, 6, 0.12);
}

.kb-preview-list {
  margin-top: 18px;
  border-radius: 18px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
}

.kb-preview-head {
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border-soft);
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.kb-preview-items {
  display: flex;
  flex-direction: column;
}

.kb-preview-item,
.kb-preview-more {
  padding: 12px 14px;
}

.kb-preview-item + .kb-preview-item,
.kb-preview-more {
  border-top: 1px solid var(--color-border-soft);
}

.kb-preview-name {
  color: var(--color-text);
  font-size: 13px;
  font-weight: 600;
}

.kb-preview-more,
.kb-warning-inline {
  color: var(--color-warning-strong);
  font-size: 13px;
}

.kb-warning-inline {
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: 14px;
  background: var(--color-surface);
  border: 1px solid var(--color-warning-border);
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
  min-height: 44px;
  padding: 0 16px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

.kb-btn-secondary {
  background: var(--color-surface);
  color: var(--color-text);
}

.kb-btn-danger {
  background: var(--color-danger);
  color: var(--color-surface);
  border-color: var(--color-danger);
}

.kb-btn:disabled,
.kb-modal-close:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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

  .kb-migration-stats {
    grid-template-columns: minmax(0, 1fr);
  }

  .kb-modal-actions {
    flex-direction: column-reverse;
  }

  .kb-btn {
    width: 100%;
  }
}
</style>
