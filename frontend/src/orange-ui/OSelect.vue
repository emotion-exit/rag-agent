<script setup lang="ts">
import { DownOutlined } from '@ant-design/icons-vue';
import { computed } from 'vue';
import { cn } from '@/utils/cn';

export interface OSelectOption {
  label: string;
  value: string | number;
}

const props = withDefaults(
  defineProps<{
    modelValue?: string | number;
    options?: OSelectOption[];
    disabled?: boolean;
    htmlClass?: string;
  }>(),
  {
    modelValue: '',
    options: () => [],
    disabled: false,
    htmlClass: ''
  }
);

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const classes = computed(() =>
  cn(
    'relative flex min-h-11 items-center rounded-(--oui-radius-md) border border-(--oui-color-border-soft) bg-(--oui-color-surface) px-4 transition duration-200 focus-within:border-(--oui-color-border-strong) focus-within:shadow-[0_0_0_4px_rgba(24,24,27,0.06)]',
    props.disabled &&
      'cursor-not-allowed bg-(--oui-color-surface-soft) opacity-70',
    props.htmlClass
  )
);
</script>

<template>
  <div :class="classes">
    <select
      :value="props.modelValue"
      :disabled="props.disabled"
      class="w-full appearance-none border-0 bg-transparent pr-7 text-[14px] leading-6 text-(--oui-color-text) outline-none"
      @change="
        emit('update:modelValue', ($event.target as HTMLSelectElement).value)
      ">
      <slot>
        <option
          v-for="option in props.options"
          :key="option.value"
          :value="option.value">
          {{ option.label }}
        </option>
      </slot>
    </select>
    <DownOutlined
      class="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-xs text-(--oui-color-text-muted)" />
  </div>
</template>
