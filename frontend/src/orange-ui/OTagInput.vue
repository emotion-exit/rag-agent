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
      'group flex min-h-12 flex-wrap items-center gap-2 rounded-[16px] border border-black/8 bg-linear-to-b from-white to-[rgba(248,248,249,0.96)] px-3.5 py-2.5 transition-all duration-300 shadow-[inset_0_1px_0_rgba(255,255,255,0.88),inset_0_-1px_0_rgba(24,24,27,0.02),0_6px_18px_rgba(24,24,27,0.04)] hover:border-black/12 hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.92),inset_0_-1px_0_rgba(24,24,27,0.03),0_10px_24px_rgba(24,24,27,0.06)] focus-within:-translate-y-[1px] focus-within:border-black/18 focus-within:shadow-[0_0_0_4px_rgba(24,24,27,0.06),inset_0_1px_0_rgba(255,255,255,0.92),0_12px_28px_rgba(24,24,27,0.08)]',
      props.disabled &&
        'cursor-not-allowed bg-(--oui-color-surface-soft) opacity-60 shadow-none hover:border-black/8 hover:shadow-none'
    ]">
    <span
      v-for="tag in tagItems"
      :key="tag"
      class="inline-flex items-center gap-1.5 rounded-full border border-black/6 bg-(--oui-color-primary-soft) px-3 py-1 text-xs font-medium text-(--oui-color-heading) shadow-[inset_0_1px_0_rgba(255,255,255,0.7)] transition-all duration-200 hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.7),0_2px_8px_rgba(24,24,27,0.06)]">
      <span>{{ tag }}</span>
      <button
        type="button"
        class="inline-flex h-4 w-4 items-center justify-center rounded-full text-(--oui-color-text-muted) transition-all duration-200 hover:bg-black/10 hover:text-(--oui-color-heading) hover:scale-110 active:scale-90"
        :disabled="props.disabled"
        @click="removeTag(tag)">
        <MinusCircleOutlined />
      </button>
    </span>
    <input
      v-model="localInput"
      :disabled="props.disabled"
      :placeholder="props.placeholder"
      class="min-w-40 flex-1 border-0 bg-transparent p-0 text-sm font-medium leading-6 text-(--oui-color-text) outline-none placeholder:font-normal placeholder:text-(--oui-color-text-subtle)"
      @keydown="handleKeydown"
      @blur="commitPendingTags" />
  </div>
</template>
