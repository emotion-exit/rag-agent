<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    label?: string;
    help?: string;
    error?: string;
    required?: boolean;
    optionalLabel?: string;
  }>(),
  {
    label: '',
    help: '',
    error: '',
    required: false,
    optionalLabel: ''
  }
);
</script>

<template>
  <label class="flex flex-col gap-2.5">
    <span
      v-if="props.label || $slots.label"
      class="flex items-center gap-2 text-[13px] font-semibold tracking-[0.01em] text-(--oui-color-heading)">
      <slot name="label">{{ props.label }}</slot>
      <span v-if="props.required" class="text-(--oui-color-danger)">*</span>
      <span
        v-else-if="props.optionalLabel"
        class="inline-flex items-center rounded-full bg-(--oui-color-surface-soft) px-2 py-0.5 text-[11px] font-medium text-(--oui-color-text-muted)">
        {{ props.optionalLabel }}
      </span>
    </span>
    <slot />
    <span
      v-if="props.error"
      class="text-[12px] leading-relaxed text-(--oui-color-danger)">
      {{ props.error }}
    </span>
    <span
      v-else-if="props.help"
      class="text-[12px] leading-relaxed text-(--oui-color-text-muted)">
      {{ props.help }}
    </span>
  </label>
</template>
