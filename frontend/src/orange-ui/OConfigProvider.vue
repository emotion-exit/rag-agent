<script setup lang="ts">
import { computed, provide, ref, watch } from 'vue';
import OToastViewport from './OToastViewport.vue';
import {
  orangeThemeKey,
  resolveOrangeTheme,
  toOrangeThemeVars,
  type OrangeThemeTokens
} from './theme';
import { createOToastApi, orangeToastKey } from './useOToast';

const props = withDefaults(
  defineProps<{
    theme?: Partial<OrangeThemeTokens>;
    class?: string;
  }>(),
  {
    theme: undefined,
    class: ''
  }
);

const themeRef = ref(resolveOrangeTheme(props.theme));
const toast = createOToastApi();

watch(
  () => props.theme,
  (nextTheme) => {
    themeRef.value = resolveOrangeTheme(nextTheme);
  },
  { immediate: true, deep: true }
);

provide(orangeThemeKey, themeRef);
provide(orangeToastKey, toast);

const themeVars = computed(() => toOrangeThemeVars(themeRef.value));
</script>

<template>
  <div
    data-orange-ui-provider
    :class="[
      'min-h-screen bg-(--oui-color-bg) text-(--oui-color-text)',
      props.class
    ]"
    :style="themeVars">
    <slot />
    <OToastViewport :items="toast.items.value" @remove="toast.remove" />
  </div>
</template>
