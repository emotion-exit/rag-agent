<script setup lang="ts">
import {
  CheckCircleOutlined,
  InfoCircleOutlined,
  WarningOutlined
} from '@ant-design/icons-vue';

const props = withDefaults(
  defineProps<{
    tone?: 'success' | 'error' | 'warning' | 'info';
    title?: string;
    htmlClass?: string;
  }>(),
  {
    tone: 'info',
    title: '',
    htmlClass: ''
  }
);

function iconForTone(tone: string) {
  if (tone === 'success') return CheckCircleOutlined;
  if (tone === 'warning' || tone === 'error') return WarningOutlined;
  return InfoCircleOutlined;
}
</script>

<template>
  <div
    :class="[
      'grid grid-cols-[auto_minmax(0,1fr)] gap-3.5 rounded-(--oui-radius-md) border px-5 py-4',
      props.tone === 'success' &&
        'border-(--oui-color-success-border) bg-(--oui-color-success-soft)',
      props.tone === 'warning' &&
        'border-(--oui-color-warning-border) bg-(--oui-color-warning-soft)',
      props.tone === 'error' &&
        'border-(--oui-color-danger-border) bg-(--oui-color-danger-soft)',
      props.tone === 'info' &&
        'border-(--oui-color-border) bg-(--oui-color-surface)',
      props.htmlClass
    ]">
    <component
      :is="iconForTone(props.tone)"
      :class="[
        'mt-0.5 text-base',
        props.tone === 'success' && 'text-(--oui-color-success)',
        props.tone === 'warning' && 'text-(--oui-color-warning)',
        props.tone === 'error' && 'text-(--oui-color-danger)',
        props.tone === 'info' && 'text-(--oui-color-text-secondary)'
      ]" />
    <div>
      <div
        v-if="props.title"
        class="text-sm font-semibold leading-relaxed text-(--oui-color-heading)">
        {{ props.title }}
      </div>
      <div class="text-sm leading-relaxed text-(--oui-color-text-secondary)">
        <slot />
      </div>
    </div>
  </div>
</template>
