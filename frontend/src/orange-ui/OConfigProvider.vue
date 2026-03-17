<script setup lang="ts">
defineOptions({
  inheritAttrs: false
});

import { computed, provide, ref, useAttrs, watch } from 'vue';
import OToastViewport from './OToastViewport.vue';
import {
  orangeThemeKey,
  resolveOrangeTheme,
  toOrangeThemeVars,
  type OrangeThemeTokens
} from './theme';
import { createOToastApi, orangeToastKey } from './useOToast';

const attrs = useAttrs();

const props = withDefaults(
  defineProps<{
    theme?: Partial<OrangeThemeTokens>;
  }>(),
  {
    theme: undefined
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

const rootAttrs = computed(() => {
  const { class: _class, ...rest } = attrs;
  return rest;
});
</script>

<template>
  <div
    v-bind="rootAttrs"
    data-orange-ui-provider
    :class="[
      'min-h-screen bg-(--oui-color-bg) text-(--oui-color-text)',
      attrs.class
    ]"
    :style="themeVars">
    <slot />
    <OToastViewport :items="toast.items.value" @remove="toast.remove" />
  </div>
</template>
