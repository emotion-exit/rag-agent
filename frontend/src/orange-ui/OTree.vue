<script setup lang="ts">
import {
  CaretDownOutlined,
  CaretRightOutlined,
  FolderOpenOutlined
} from '@ant-design/icons-vue';

type OTreeItem = Record<string, any>;

const props = withDefaults(
  defineProps<{
    items: OTreeItem[];
    selectedKey?: string;
    expandedKeys?: string[];
    getKey: (item: OTreeItem) => string;
    getLabel: (item: OTreeItem) => string;
    getDescription?: (item: OTreeItem) => string;
    getCount?: (item: OTreeItem) => string | number;
    getChildren?: (item: OTreeItem) => OTreeItem[];
    getDepth?: (item: OTreeItem) => number;
    emptyText?: string;
  }>(),
  {
    selectedKey: '',
    expandedKeys: () => [],
    getDescription: undefined,
    getCount: undefined,
    getChildren: undefined,
    getDepth: undefined,
    emptyText: '暂无数据'
  }
);

const emit = defineEmits<{
  select: [item: OTreeItem];
  toggle: [item: OTreeItem];
}>();

function hasChildren(item: OTreeItem) {
  return (props.getChildren?.(item) || []).length > 0;
}

function isExpanded(item: OTreeItem) {
  return props.expandedKeys.includes(props.getKey(item));
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <div
      v-if="props.items.length === 0"
      class="rounded-(--oui-radius-md) border border-dashed border-(--oui-color-border) px-4 py-6 text-center text-sm text-(--oui-color-text-muted)">
      {{ props.emptyText }}
    </div>
    <div
      v-for="item in props.items"
      :key="props.getKey(item)"
      class="flex items-start gap-2"
      :style="{ paddingLeft: `${(props.getDepth?.(item) || 0) * 12}px` }">
      <button
        type="button"
        class="mt-1 inline-flex h-6 w-6 items-center justify-center rounded-full text-(--oui-color-text-muted) transition hover:bg-black/5 hover:text-(--oui-color-heading)"
        :class="!hasChildren(item) && 'opacity-0 pointer-events-none'"
        @click="emit('toggle', item)">
        <CaretDownOutlined v-if="hasChildren(item) && isExpanded(item)" />
        <CaretRightOutlined v-else-if="hasChildren(item)" />
      </button>
      <button
        type="button"
        :class="[
          'flex flex-1 items-start justify-between gap-3 rounded-(--oui-radius-md) border px-3 py-3 text-left transition',
          props.selectedKey === props.getKey(item)
            ? 'border-(--oui-color-primary) bg-(--oui-color-primary-soft)'
            : 'border-transparent bg-transparent hover:border-(--oui-color-border-soft) hover:bg-white/60'
        ]"
        @click="emit('select', item)">
        <div class="flex min-w-0 items-start gap-3">
          <slot name="icon" :item="item">
            <FolderOpenOutlined class="mt-1 text-(--oui-color-text-muted)" />
          </slot>
          <div class="min-w-0">
            <div
              class="truncate text-sm font-medium text-(--oui-color-heading)">
              {{ props.getLabel(item) }}
            </div>
            <div
              v-if="props.getDescription?.(item)"
              class="truncate text-xs leading-5 text-(--oui-color-text-muted)">
              {{ props.getDescription?.(item) }}
            </div>
          </div>
        </div>
        <span
          v-if="props.getCount"
          class="shrink-0 text-xs font-medium text-(--oui-color-text-muted)">
          {{ props.getCount(item) }}
        </span>
      </button>
    </div>
  </div>
</template>
