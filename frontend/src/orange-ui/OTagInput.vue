<script setup lang="ts">
import { MinusCircleOutlined } from '@ant-design/icons-vue';
import { computed, ref, watch } from 'vue';

const props = withDefaults(
  defineProps<{
    modelValue?: string;
    disabled?: boolean;
    placeholder?: string;
  }>(),
  {
    modelValue: '',
    disabled: false,
    placeholder: '输入后按回车生成标签'
  }
);

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const localInput = ref('');

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

const tagItems = computed(() => parseTagList(props.modelValue));

watch(
  () => props.modelValue,
  () => {
    if (!props.disabled) return;
    localInput.value = '';
  }
);

function syncTagField(tags: string[]) {
  emit('update:modelValue', Array.from(new Set(tags)).join(', '));
}

function commitPendingTags() {
  const pendingTags = parseTagList(localInput.value);
  if (pendingTags.length === 0) return;
  syncTagField([...tagItems.value, ...pendingTags]);
  localInput.value = '';
}

function removeTag(tag: string) {
  syncTagField(tagItems.value.filter((item) => item !== tag));
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ',' || event.key === '，') {
    event.preventDefault();
    commitPendingTags();
  }
}
</script>

<template>
  <div
    :class="[
      'flex min-h-11 flex-wrap items-center gap-2 rounded-(--oui-radius-md) border border-(--oui-color-border-soft) bg-(--oui-color-surface) px-3 py-2 transition duration-200 focus-within:border-(--oui-color-border-strong) focus-within:shadow-[0_0_0_4px_rgba(24,24,27,0.06)]',
      props.disabled &&
        'cursor-not-allowed bg-(--oui-color-surface-soft) opacity-70'
    ]">
    <span
      v-for="tag in tagItems"
      :key="tag"
      class="inline-flex items-center gap-1 rounded-full bg-(--oui-color-primary-soft) px-3 py-1 text-xs font-medium text-(--oui-color-heading)">
      <span>{{ tag }}</span>
      <button
        type="button"
        class="inline-flex h-4 w-4 items-center justify-center rounded-full text-(--oui-color-text-muted) transition hover:bg-black/5 hover:text-(--oui-color-heading)"
        :disabled="props.disabled"
        @click="removeTag(tag)">
        <MinusCircleOutlined />
      </button>
    </span>
    <input
      v-model="localInput"
      :disabled="props.disabled"
      :placeholder="props.placeholder"
      class="min-w-40 flex-1 border-0 bg-transparent p-0 text-sm leading-6 text-(--oui-color-text) outline-none placeholder:text-(--oui-color-text-subtle)"
      @keydown="handleKeydown"
      @blur="commitPendingTags" />
  </div>
</template>
