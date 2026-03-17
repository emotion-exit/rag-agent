<script setup lang="ts">
import { computed } from 'vue';
import { cn } from '@/utils/cn';

const props = withDefaults(
  defineProps<{
    title: string;
    description?: string;
    iconClass?: string;
    class?: string;
  }>(),
  {
    description: undefined,
    iconClass: 'bg-brand-soft text-heading p-5 text-[46px]'
  }
);
</script>

<template>
  <div
    :class="
      cn(
        'flex flex-col items-center justify-center text-center animate-o-fade-in py-12',
        props.class
      )
    ">
    <div class="mb-4 flex flex-col items-center gap-4">
      <div
        v-if="$slots.icon || true"
        :class="
          cn('rounded-full flex justify-center items-center', props.iconClass)
        ">
        <slot name="icon" />
      </div>
      <h2
        class="m-0 text-2xl font-bold leading-tight tracking-tight text-heading max-sm:text-xl">
        {{ props.title }}
      </h2>
    </div>
    <p
      v-if="props.description || $slots.description"
      class="mb-8 text-sm leading-relaxed text-muted max-w-[460px]">
      <slot name="description">{{ props.description }}</slot>
    </p>
    <div v-if="$slots.default" class="w-full max-w-[560px]">
      <slot />
    </div>
  </div>
</template>
