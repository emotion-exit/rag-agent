<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type {
  KnowledgeSpace,
  KnowledgeSpaceCreateForm
} from '@/types/knowledgeBase';
import {
  OAlert,
  OFormItem,
  OFormSection,
  OInput,
  OModal,
  OSelect,
  OTagInput,
  OTextarea
} from '@/orange-ui';

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

const parentOptions = computed(() => [
  { label: '创建顶级空间', value: '' },
  ...props.spaces.map((space) => ({
    label: space.path,
    value: space.space_id
  }))
]);

const categoryOptions = computed(() => [
  { label: '不指定分类', value: '' },
  ...props.categoryOptions.map((item) => ({ label: item, value: item }))
]);

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
        description="先确定空间层级与命名，方便后续目录结构与权限范围管理。"
        :badge="localForm.parent_id ? '子空间模式' : '顶级空间模式'">
        <div class="grid grid-cols-2 gap-3.5 max-md:grid-cols-1">
          <OFormItem label="父级空间" optional-label="选填">
            <OSelect
              v-model="localForm.parent_id"
              :options="parentOptions"
              :disabled="submitting" />
          </OFormItem>

          <OFormItem label="空间名称" :required="true">
            <OInput
              v-model="localForm.name"
              :disabled="submitting"
              placeholder="例如：人事制度、合同管理、售后 SOP" />
          </OFormItem>

          <OFormItem label="分类" optional-label="选填">
            <OSelect
              v-model="localForm.category"
              :options="categoryOptions"
              :disabled="submitting" />
          </OFormItem>

          <OFormItem label="主题" optional-label="选填">
            <OInput
              v-model="localForm.topic"
              :disabled="submitting"
              placeholder="例如：合同审批流程、离职办理、项目复盘" />
          </OFormItem>
        </div>
      </OFormSection>

      <OFormSection
        title="检索元数据"
        description="标签、版本和说明会参与后续文档继承与检索语义补全。"
        tone="muted">
        <div class="grid grid-cols-2 gap-3.5 max-md:grid-cols-1">
          <OFormItem
            label="标签"
            optional-label="选填"
            class="col-span-2 max-md:col-span-1">
            <OTagInput v-model="localForm.tags" :disabled="submitting" />
          </OFormItem>

          <OFormItem label="版本 / 时效" optional-label="选填">
            <OInput
              v-model="localForm.version_label"
              :disabled="submitting"
              placeholder="例如：V2.1、2026Q1" />
          </OFormItem>

          <div class="hidden max-md:block" />

          <OFormItem
            label="说明"
            optional-label="选填"
            class="col-span-2 max-md:col-span-1">
            <OTextarea
              v-model="localForm.description"
              class="min-h-32"
              :rows="4"
              :disabled="submitting"
              placeholder="补充这个知识空间的适用范围、边界或维护说明" />
          </OFormItem>
        </div>
      </OFormSection>
    </div>
  </OModal>
</template>
