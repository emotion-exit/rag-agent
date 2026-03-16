<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    label?: string;
    help?: string;
    error?: string;
    required?: boolean;
    optionalLabel?: string;
    htmlClass?: string;
  }>(),
  {
    label: '',
    help: '',
    error: '',
    required: false,
    optionalLabel: '',
    htmlClass: ''
  }
);
</script>

<template>
  <label :class="['flex flex-col gap-3', props.htmlClass]">
    <span
      v-if="props.label || $slots.label"
      class="flex items-center gap-2 text-sm font-semibold text-(--oui-color-heading)">
      <slot name="label">{{ props.label }}</slot>
      <span v-if="props.required" class="text-(--oui-color-danger)">*</span>
      <span
        v-else-if="props.optionalLabel"
        class="text-xs font-normal text-(--oui-color-text-muted)">
        {{ props.optionalLabel }}
      </span>
    </span>
    <slot />
    <span
      v-if="props.error"
      class="text-xs leading-relaxed text-(--oui-color-danger)">
      {{ props.error }}
    </span>
    <span
      v-else-if="props.help"
      class="text-xs leading-relaxed text-(--oui-color-text-muted)">
      {{ props.help }}
    </span>
  </label>
</template>
