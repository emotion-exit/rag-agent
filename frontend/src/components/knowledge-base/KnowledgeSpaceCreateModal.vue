<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { KnowledgeSpaceCreateForm } from '@/types/knowledgeBase';
import {
  OFormItem,
  OFormSection,
  OInput,
  OModal,
  OTagInput,
  OTextarea
} from '@/orange-ui';

defineOptions({
  name: 'KnowledgeSpaceCreateModal'
});

const props = defineProps<{
  visible: boolean;
  submitting: boolean;
  mode: 'create' | 'edit';
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
  props.mode === 'edit' ? '编辑知识库' : '新建知识库'
);

const modalSubtitle = computed(() =>
  props.mode === 'edit'
    ? '更新知识库的基础信息。'
    : '创建一个新的知识库用于管理文档。'
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
  <OModal
    :visible="visible"
    :title="modalTitle"
    :subtitle="modalSubtitle"
    :closable="!submitting"
    cancel-text="取消"
    :cancel-disabled="submitting"
    :confirm-text="modalTitle"
    :confirm-loading="submitting"
    width="min(760px, 100%)"
    @confirm="submitForm"
    @close="requestClose">
    <div class="space-y-4.5">
      <OFormSection
        title="基础信息"
        description="设置知识库名称。"
        :badge="props.mode === 'edit' ? '编辑模式' : '新建模式'">
        <div class="grid grid-cols-1 gap-3.5">
          <OFormItem label="空间名称" :required="true">
            <OInput
              v-model="localForm.name"
              :disabled="submitting"
              placeholder="例如：人事制度、合同管理" />
          </OFormItem>
        </div>
      </OFormSection>

      <OFormSection
        title="扩展信息"
        description="添加标签和说明以优化检索分类。"
        tone="muted">
        <div class="grid grid-cols-1 gap-3.5">
          <OFormItem
            label="标签"
            optional-label="选填"
            class="max-md:col-span-1">
            <OTagInput v-model="localForm.tags" :disabled="submitting" />
          </OFormItem>

          <OFormItem
            label="说明"
            optional-label="选填"
            class="max-md:col-span-1">
            <OTextarea
              v-model="localForm.description"
              class="min-h-32"
              :rows="4"
              :disabled="submitting"
              placeholder="简要描述此知识库的用途或内容" />
          </OFormItem>
        </div>
      </OFormSection>
    </div>
  </OModal>
</template>
