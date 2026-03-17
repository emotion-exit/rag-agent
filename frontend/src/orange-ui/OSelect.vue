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
  }>(),
  {
    modelValue: '',
    options: () => [],
    disabled: false
  }
);

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const classes = computed(() =>
  cn(
    'group relative flex min-h-12 items-center rounded-[16px] border border-black/8 bg-linear-to-b from-white to-[rgba(248,248,249,0.96)] px-4 transition-all duration-300 shadow-[inset_0_1px_0_rgba(255,255,255,0.88),inset_0_-1px_0_rgba(24,24,27,0.02),0_6px_18px_rgba(24,24,27,0.04)] hover:border-black/12 hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.92),inset_0_-1px_0_rgba(24,24,27,0.03),0_10px_24px_rgba(24,24,27,0.06)] focus-within:-translate-y-[1px] focus-within:border-black/18 focus-within:shadow-[0_0_0_4px_rgba(24,24,27,0.06),inset_0_1px_0_rgba(255,255,255,0.92),0_12px_28px_rgba(24,24,27,0.08)]',
    props.disabled &&
      'cursor-not-allowed bg-(--oui-color-surface-soft) opacity-60 shadow-none hover:border-black/8 hover:shadow-none'
  )
);
</script>

<template>
  <div :class="classes">
    <select
      :value="props.modelValue"
      :disabled="props.disabled"
      class="w-full appearance-none border-0 bg-transparent pr-12 text-[14px] font-medium leading-6 text-(--oui-color-text) outline-none"
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
    <span
      class="pointer-events-none absolute right-3 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full border border-black/6 bg-white/80 text-[11px] text-(--oui-color-text-muted) shadow-[inset_0_1px_0_rgba(255,255,255,0.85)] transition-all duration-200 group-focus-within:border-black/10 group-focus-within:text-(--oui-color-heading)">
      <DownOutlined />
    </span>
  </div>
</template>
