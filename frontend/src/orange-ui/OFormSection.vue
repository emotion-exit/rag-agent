<script setup lang="ts">
import { computed } from 'vue';
import { cn } from '@/utils/cn';
import OCard from './OCard.vue';

const props = withDefaults(
  defineProps<{
    title?: string;
    description?: string;
    badge?: string;
    tone?: 'default' | 'muted' | 'success' | 'warning' | 'danger';
    padding?: 'none' | 'sm' | 'md' | 'lg';
    headerSpacing?: 'default' | 'compact';
  }>(),
  {
    title: '',
    description: '',
    badge: '',
    tone: 'default',
    padding: 'lg',
    headerSpacing: 'default'
  }
);

const badgeClass = computed(() =>
  cn(
    'inline-flex items-center rounded-full px-3 py-1 text-xs font-medium',
    props.tone === 'muted' &&
      'bg-(--oui-color-surface) text-(--oui-color-heading) shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]',
    props.tone === 'success' &&
      'bg-(--oui-color-success-soft) text-(--oui-color-success)',
    props.tone === 'warning' &&
      'bg-(--oui-color-warning-soft) text-(--oui-color-warning)',
    props.tone === 'danger' &&
      'bg-(--oui-color-danger-soft) text-(--oui-color-danger)',
    props.tone === 'default' &&
      'bg-(--oui-color-primary-soft) text-(--oui-color-heading)'
  )
);
</script>

<template>
  <OCard :padding="props.padding" :tone="props.tone">
    <div
      v-if="props.title || props.description || props.badge || $slots.header"
      :class="
        cn(
          'mb-4 flex items-start justify-between gap-3 max-md:flex-col',
          props.headerSpacing === 'compact' && 'mb-0'
        )
      ">
      <slot name="header">
        <div>
          <div
            v-if="props.title"
            class="text-sm font-semibold text-(--oui-color-heading)">
            {{ props.title }}
          </div>
          <div
            v-if="props.description"
            class="mt-1 text-xs leading-5 text-(--oui-color-text-muted)">
            {{ props.description }}
          </div>
        </div>
        <div v-if="props.badge" :class="badgeClass">
          {{ props.badge }}
        </div>
      </slot>
    </div>

    <div>
      <slot />
    </div>
  </OCard>
</template>
