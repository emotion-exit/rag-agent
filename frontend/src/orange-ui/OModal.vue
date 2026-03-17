<script setup lang="ts">
defineOptions({
  inheritAttrs: false
});

import { CloseOutlined } from '@ant-design/icons-vue';
import { computed, useAttrs } from 'vue';
import { cn } from '@/utils/cn';
import OButton from './OButton.vue';

const attrs = useAttrs();

const props = withDefaults(
  defineProps<{
    visible: boolean;
    title?: string;
    subtitle?: string;
    width?: string;
    closable?: boolean;
    closeOnMask?: boolean;
    cancelText?: string;
    confirmText?: string;
    confirmVariant?: 'primary' | 'secondary' | 'danger' | 'warning' | 'ghost';
    cancelDisabled?: boolean;
    confirmDisabled?: boolean;
    confirmLoading?: boolean;
    class?: any;
  }>(),
  {
    title: '',
    subtitle: '',
    width: 'min(760px, 100%)',
    closable: true,
    closeOnMask: false,
    cancelText: '',
    confirmText: '',
    confirmVariant: 'primary',
    cancelDisabled: false,
    confirmDisabled: false,
    confirmLoading: false
  }
);

const emit = defineEmits<{
  close: [];
  confirm: [];
}>();

const panelStyle = computed(() => ({ width: props.width }));

const panelAttrs = computed(() => {
  const { class: _class, ...rest } = attrs;
  return rest;
});

function requestClose() {
  if (!props.closable) return;
  emit('close');
}

function requestConfirm() {
  if (props.confirmDisabled || props.confirmLoading) return;
  emit('confirm');
}
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0">
      <div
        v-if="props.visible"
        class="fixed inset-0 z-9999 flex items-center justify-center bg-black/42 p-6 backdrop-blur-xl backdrop-saturate-150"
        @click="props.closeOnMask ? requestClose() : undefined">
        <Transition
          enter-active-class="transition duration-200 ease-out"
          enter-from-class="translate-y-2 scale-[0.98] opacity-0"
          enter-to-class="translate-y-0 scale-100 opacity-100"
          leave-active-class="transition duration-150 ease-in"
          leave-from-class="translate-y-0 scale-100 opacity-100"
          leave-to-class="translate-y-2 scale-[0.98] opacity-0">
          <div
            v-if="props.visible"
            v-bind="panelAttrs"
            :style="panelStyle"
            :class="
              cn(
                'flex max-h-[88vh] flex-col overflow-hidden rounded-3xl border border-white/90 bg-[rgba(255,255,255,0.98)] shadow-[0_20px_60px_rgba(24,24,27,0.16),inset_0_1px_0_rgba(255,255,255,0.9)] backdrop-blur-3xl backdrop-saturate-200',
                props.class
              )
            "
            @click.stop>
            <div
              v-if="props.title || props.subtitle || $slots.header"
              class="shrink-0 px-8 pt-8">
              <div class="flex items-start justify-between gap-4">
                <slot name="header">
                  <div>
                    <div
                      v-if="props.title"
                      class="text-xl font-bold text-(--oui-color-heading)">
                      {{ props.title }}
                    </div>
                    <div
                      v-if="props.subtitle"
                      class="mt-1.5 text-[13px] leading-6 text-(--oui-color-text-muted)">
                      {{ props.subtitle }}
                    </div>
                  </div>
                </slot>
                <button
                  v-if="props.closable"
                  type="button"
                  class="inline-flex h-9 w-9 items-center justify-center rounded-full bg-black/4 text-(--oui-color-text-secondary) transition-all duration-200 hover:bg-black/8 hover:text-(--oui-color-heading) hover:scale-105 active:scale-95"
                  @click="requestClose">
                  <CloseOutlined />
                </button>
              </div>
            </div>

            <div
              :class="[
                'min-h-0 flex-1 overflow-y-auto px-8',
                props.title || props.subtitle || $slots.header
                  ? 'pt-5'
                  : 'pt-8',
                $slots.footer || props.cancelText || props.confirmText
                  ? 'pb-5'
                  : 'pb-8'
              ]">
              <slot />
            </div>

            <div
              v-if="$slots.footer || props.cancelText || props.confirmText"
              class="shrink-0 px-8 pb-8 pt-5">
              <div class="flex justify-end gap-2.5">
                <slot name="footer">
                  <OButton
                    v-if="props.cancelText"
                    variant="secondary"
                    :disabled="props.cancelDisabled"
                    @click="requestClose">
                    {{ props.cancelText }}
                  </OButton>
                  <OButton
                    v-if="props.confirmText"
                    :variant="props.confirmVariant"
                    :disabled="props.confirmDisabled"
                    :loading="props.confirmLoading"
                    @click="requestConfirm">
                    {{ props.confirmText }}
                  </OButton>
                </slot>
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>
