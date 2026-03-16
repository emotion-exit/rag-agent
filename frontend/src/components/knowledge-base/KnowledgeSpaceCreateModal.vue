<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import {
  CloseOutlined,
  LoadingOutlined,
  PlusOutlined
} from '@ant-design/icons-vue';
import type {
  KnowledgeSpace,
  KnowledgeSpaceCreateForm
} from '@/types/knowledgeBase';

defineOptions({
  name: 'KnowledgeSpaceCreateModal'
});

const props = defineProps<{
  visible: boolean;
  submitting: boolean;
  spaces: KnowledgeSpace[];
  categoryOptions: string[];
  initialForm: KnowledgeSpaceCreateForm;
}>();

const emit = defineEmits<{
  close: [];
  submit: [payload: KnowledgeSpaceCreateForm];
}>();

const localForm = ref<KnowledgeSpaceCreateForm>({ ...props.initialForm });

watch(
  () => [props.visible, props.initialForm] as const,
  ([visible]) => {
    if (!visible) return;
    localForm.value = { ...props.initialForm };
  },
  { deep: true }
);

const modalTitle = computed(() =>
  localForm.value.parent_id ? '创建子空间' : '创建顶级空间'
);

const modalSubtitle = computed(() =>
  localForm.value.parent_id
    ? '子空间用于继续细分目录，保持知识结构清晰。'
    : '顶级空间适合按业务线、部门或主题建立一级目录。'
);

function requestClose() {
  if (props.submitting) return;
  emit('close');
}

function submitForm() {
  emit('submit', { ...localForm.value });
}
</script>

<template>
  <Teleport to="body">
    <Transition name="kb-modal-fade">
      <div v-if="visible" class="kb-modal-backdrop" @click.self="requestClose">
        <div class="kb-modal-panel">
          <div class="kb-modal-head">
            <div>
              <div class="kb-modal-title">{{ modalTitle }}</div>
              <div class="kb-modal-subtitle">{{ modalSubtitle }}</div>
            </div>
            <button
              type="button"
              class="kb-modal-close"
              :disabled="submitting"
              @click="requestClose">
              <CloseOutlined />
            </button>
          </div>

          <div class="kb-form-grid">
            <label class="kb-field-block">
              <span class="kb-field-label">父级空间</span>
              <select
                v-model="localForm.parent_id"
                class="kb-field-input kb-field-select"
                :disabled="submitting">
                <option value="">创建顶级空间</option>
                <option
                  v-for="space in spaces"
                  :key="space.space_id"
                  :value="space.space_id">
                  {{ space.path }}
                </option>
              </select>
            </label>

            <label class="kb-field-block">
              <span class="kb-field-label">空间名称</span>
              <input
                v-model="localForm.name"
                class="kb-field-input"
                type="text"
                placeholder="例如：人事制度、合同管理、售后 SOP"
                :disabled="submitting" />
            </label>

            <label class="kb-field-block">
              <span class="kb-field-label">分类</span>
              <select
                v-model="localForm.category"
                class="kb-field-input kb-field-select"
                :disabled="submitting">
                <option
                  v-for="option in categoryOptions"
                  :key="option"
                  :value="option">
                  {{ option }}
                </option>
              </select>
            </label>

            <label class="kb-field-block">
              <span class="kb-field-label">主题</span>
              <input
                v-model="localForm.topic"
                class="kb-field-input"
                type="text"
                placeholder="例如：合同审批流程、离职办理、项目复盘"
                :disabled="submitting" />
            </label>

            <label class="kb-field-block">
              <span class="kb-field-label">标签</span>
              <input
                v-model="localForm.tags"
                class="kb-field-input"
                type="text"
                placeholder="多个标签用逗号分隔"
                :disabled="submitting" />
            </label>

            <label class="kb-field-block">
              <span class="kb-field-label">版本 / 时效</span>
              <input
                v-model="localForm.version_label"
                class="kb-field-input"
                type="text"
                placeholder="例如：V2.1、2026Q1"
                :disabled="submitting" />
            </label>
          </div>

          <label class="kb-field-block kb-field-block-full">
            <span class="kb-field-label">说明</span>
            <textarea
              v-model="localForm.description"
              class="kb-field-input kb-field-textarea"
              rows="4"
              placeholder="补充这个知识空间的适用范围、边界或维护说明"
              :disabled="submitting" />
          </label>

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
              class="kb-btn kb-btn-primary"
              :disabled="submitting"
              @click="submitForm">
              <LoadingOutlined v-if="submitting" class="spin" />
              <PlusOutlined v-else />
              {{ modalTitle }}
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

.kb-modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
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

.kb-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.kb-field-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kb-field-block-full {
  margin-top: 14px;
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
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}

.kb-field-input:focus {
  outline: none;
  border-color: var(--color-success);
  box-shadow: 0 0 0 3px rgba(47, 107, 79, 0.1);
}

.kb-field-select,
.kb-field-textarea {
  resize: vertical;
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

.kb-btn:disabled,
.kb-modal-close:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.kb-btn-primary {
  background: var(--color-success);
  color: var(--color-on-success);
  border-color: var(--color-success);
}

.kb-btn-secondary {
  background: var(--color-surface);
  color: var(--color-text);
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

  .kb-form-grid {
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
