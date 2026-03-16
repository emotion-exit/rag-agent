<script setup lang="ts">
import { CloseOutlined } from '@ant-design/icons-vue';
import { computed } from 'vue';
import { cn } from '@/utils/cn';

const props = withDefaults(
  defineProps<{
    visible: boolean;
    title?: string;
    subtitle?: string;
    width?: string;
    closable?: boolean;
    closeOnMask?: boolean;
    panelClass?: string;
    bodyClass?: string;
  }>(),
  {
    title: '',
    subtitle: '',
    width: 'min(760px, 100%)',
    closable: true,
    closeOnMask: false,
    panelClass: '',
    bodyClass: ''
  }
);

const emit = defineEmits<{
  close: [];
}>();

const panelStyle = computed(() => ({ width: props.width }));

function requestClose() {
  if (!props.closable) return;
  emit('close');
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
        class="fixed inset-0 z-9999 flex items-center justify-center bg-black/40 p-6 backdrop-blur-xl"
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
            :style="panelStyle"
            :class="
              cn(
                'max-h-[88vh] overflow-auto rounded-3xl border border-white/80 bg-[rgba(255,255,255,0.95)] p-8 shadow-floating backdrop-blur-2xl backdrop-saturate-200',
                props.panelClass
              )
            "
            @click.stop>
            <div
              v-if="props.title || props.subtitle || $slots.header"
              class="mb-5 flex items-start justify-between gap-4">
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
                class="inline-flex h-9 w-9 items-center justify-center rounded-full bg-black/5 text-(--oui-color-text-secondary) transition hover:bg-black/10 hover:text-(--oui-color-heading)"
                @click="requestClose">
                <CloseOutlined />
              </button>
            </div>

            <div :class="props.bodyClass">
              <slot />
            </div>

            <div v-if="$slots.footer" class="mt-5 flex justify-end gap-2.5">
              <slot name="footer" />
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>
