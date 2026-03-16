<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import {
  CloseOutlined,
  LoadingOutlined,
  MinusCircleOutlined,
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
const localTagInput = ref('');

function parseTagList(value: string) {
  return Array.from(
    new Set(
      String(value || '')
        .split(/[，,、\n]/)
        .map((item) => item.trim())
        .filter(Boolean)
    )
  );
}

const tagItems = computed(() => parseTagList(localForm.value.tags));

function syncTagField(tags: string[]) {
  localForm.value.tags = Array.from(new Set(tags)).join(', ');
}

function commitPendingTags() {
  const pendingTags = parseTagList(localTagInput.value);
  if (pendingTags.length === 0) return;

  syncTagField([...tagItems.value, ...pendingTags]);
  localTagInput.value = '';
}

function removeTag(tag: string) {
  syncTagField(tagItems.value.filter((item) => item !== tag));
}

function handleTagInputKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ',' || event.key === '，') {
    event.preventDefault();
    commitPendingTags();
  }
}

watch(
  () => [props.visible, props.initialForm] as const,
  ([visible]) => {
    if (!visible) return;
    localForm.value = { ...props.initialForm };
    localTagInput.value = '';
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
  commitPendingTags();
  emit('submit', { ...localForm.value });
}
</script>

<template>
  <Teleport to="body">
    <Transition name="kb-modal-fade">
      <div v-if="visible" class="kb-modal-backdrop">
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
              <span class="kb-field-label">
                父级空间
                <span class="kb-field-optional">选填</span>
              </span>
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
              <span class="kb-field-label">
                空间名称
                <span class="kb-required-mark">*</span>
              </span>
              <input
                v-model="localForm.name"
                class="kb-field-input"
                type="text"
                placeholder="例如：人事制度、合同管理、售后 SOP"
                :disabled="submitting" />
            </label>

            <label class="kb-field-block">
              <span class="kb-field-label">
                分类
                <span class="kb-field-optional">选填</span>
              </span>
              <input
                v-model="localForm.category"
                class="kb-field-input"
                type="text"
                placeholder="例如：制度规范、操作手册、服务流程"
                :disabled="submitting" />
            </label>

            <label class="kb-field-block">
              <span class="kb-field-label">
                主题
                <span class="kb-field-optional">选填</span>
              </span>
              <input
                v-model="localForm.topic"
                class="kb-field-input"
                type="text"
                placeholder="例如：合同审批流程、离职办理、项目复盘"
                :disabled="submitting" />
            </label>

            <label class="kb-field-block">
              <span class="kb-field-label">
                标签
                <span class="kb-field-optional">选填</span>
              </span>
              <div class="kb-tag-editor">
                <span v-for="tag in tagItems" :key="tag" class="kb-tag-chip">
                  <span>{{ tag }}</span>
                  <button
                    type="button"
                    class="kb-tag-chip-remove"
                    :disabled="submitting"
                    @click="removeTag(tag)">
                    <MinusCircleOutlined />
                  </button>
                </span>
                <input
                  v-model="localTagInput"
                  class="kb-tag-input"
                  type="text"
                  placeholder="输入后按回车生成标签"
                  :disabled="submitting"
                  @keydown="handleTagInputKeydown"
                  @blur="commitPendingTags" />
              </div>
            </label>

            <label class="kb-field-block">
              <span class="kb-field-label">
                版本 / 时效
                <span class="kb-field-optional">选填</span>
              </span>
              <input
                v-model="localForm.version_label"
                class="kb-field-input"
                type="text"
                placeholder="例如：V2.1、2026Q1"
                :disabled="submitting" />
            </label>
          </div>

          <label class="kb-field-block kb-field-block-full">
            <span class="kb-field-label">
              说明
              <span class="kb-field-optional">选填</span>
            </span>
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
  width: min(760px, 100%);
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

.kb-required-mark {
  margin-left: 4px;
  color: var(--color-warning-strong);
}

.kb-field-optional {
  margin-left: 6px;
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 500;
}

.kb-field-input {
  width: 100%;
  appearance: none;
  -webkit-appearance: none;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.7);
  color: var(--color-text);
  padding: 12px 14px;
  font: inherit;
  font-size: 14px;
  line-height: 1.5;
  transition: all 0.2s ease;
}

.kb-field-input:focus {
  outline: none;
  background: #ffffff;
  border-color: rgba(47, 107, 79, 0.4);
  box-shadow: 0 0 0 4px rgba(47, 107, 79, 0.1);
}

.kb-field-select {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%233f3f46' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 14px center;
  padding-right: 36px;
  resize: vertical;
}

.kb-tag-editor {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 48px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.7);
  padding: 8px 10px;
  transition: all 0.2s ease;
}

.kb-tag-editor:focus-within {
  background: #ffffff;
  border-color: rgba(47, 107, 79, 0.4);
  box-shadow: 0 0 0 4px rgba(47, 107, 79, 0.1);
}

.kb-tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(47, 107, 79, 0.1);
  color: var(--color-success-strong);
  font-size: 12px;
  font-weight: 600;
}

.kb-tag-chip-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 0;
}

.kb-tag-input {
  flex: 1 1 180px;
  min-width: 140px;
  min-height: 30px;
  border: none;
  background: transparent;
  color: var(--color-text);
  font: inherit;
  font-size: 14px;
  outline: none;
  padding: 0 2px;
}

.kb-tag-input::placeholder {
  color: var(--color-text-muted);
}

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

.kb-btn-primary {
  background: var(--color-success);
  color: var(--color-on-success);
  box-shadow: 0 4px 12px rgba(47, 107, 79, 0.25);
}

.kb-btn-primary:not(:disabled):hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(47, 107, 79, 0.35);
}

.kb-btn-primary:not(:disabled):active {
  transform: scale(0.98);
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
