<script setup lang="ts">
import { computed } from 'vue';
import {
  ReloadOutlined,
  FileTextOutlined,
  LoadingOutlined,
  WarningOutlined
} from '@ant-design/icons-vue';
import { OButton, OEmptyState } from '@/orange-ui';
import type { NoteListItem } from '@/types/notes';

const props = defineProps<{
  noteGroups: Array<{
    knowledgeSpace: string;
    items: NoteListItem[];
  }>;
  notesLoading: boolean;
  selectedNoteId: string;
}>();

defineEmits<{
  refresh: [];
  selectNote: [noteId: string];
}>();

const safeNoteGroups = computed(() =>
  Array.isArray(props.noteGroups) ? props.noteGroups : []
);
</script>

<template>
  <section
    class="flex min-h-130 flex-col rounded-3xl border border-black/6 bg-zinc-50/80 p-4">
    <div class="mb-3 flex items-center justify-between gap-3">
      <div>
        <div
          class="text-xs font-bold uppercase tracking-[0.16em] text-zinc-500">
          笔记列表
        </div>
        <div class="mt-1 text-xs leading-5 text-zinc-500">
          保存中的笔记会先以占位状态显示。
        </div>
      </div>
      <OButton
        variant="secondary"
        size="sm"
        class="h-8 rounded-full px-3 text-xs"
        :loading="notesLoading"
        @click="$emit('refresh')">
        <ReloadOutlined />
        刷新
      </OButton>
    </div>

    <div v-if="notesLoading && safeNoteGroups.length === 0" class="space-y-3">
      <div
        v-for="index in 4"
        :key="`note-skeleton-${index}`"
        class="rounded-2xl border border-black/5 bg-white px-4 py-4 shadow-sm">
        <div class="h-4 w-2/3 animate-pulse rounded-full bg-zinc-200"></div>
        <div
          class="mt-3 h-3 w-full animate-pulse rounded-full bg-zinc-100"></div>
        <div
          class="mt-2 h-3 w-5/6 animate-pulse rounded-full bg-zinc-100"></div>
      </div>
    </div>

    <div
      v-else-if="safeNoteGroups.length === 0"
      class="flex flex-1 items-center justify-center">
      <OEmptyState
        title="还没有保存的笔记"
        description="从聊天框底部动作点击“保存笔记”后，这里会出现可长期回看的归档。" />
    </div>

    <div v-else class="flex-1 overflow-y-auto pr-1 space-y-2">
      <section
        v-for="group in safeNoteGroups"
        :key="group.knowledgeSpace"
        class="space-y-2.5">
        <div
          class="sticky top-0 z-1 rounded-2xl bg-zinc-50/92 px-2 py-1 backdrop-blur-sm">
          <div
            class="text-[11px] font-bold uppercase tracking-[0.16em] text-zinc-400">
            {{ group.knowledgeSpace }}
          </div>
          <div class="mt-1 text-[11px] text-zinc-500">
            {{ group.items.length }} 条笔记
          </div>
        </div>

        <button
          v-for="note in group.items"
          :key="note.note_id"
          type="button"
          :class="[
            'w-full rounded-2xl border px-4 py-3 text-left transition-all duration-200',
            selectedNoteId === note.note_id
              ? 'border-zinc-900 bg-white shadow-[0_12px_24px_rgba(24,24,27,0.08)]'
              : 'border-black/6 bg-white/90 hover:border-black/12 hover:bg-white'
          ]"
          @click="$emit('selectNote', note.note_id)">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span
                  v-if="note.status === 'pending'"
                  class="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] font-semibold text-zinc-600">
                  <LoadingOutlined class="animate-spin" />
                  保存中
                </span>
                <span
                  v-else-if="note.status === 'failed'"
                  class="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-semibold text-red-700">
                  <WarningOutlined />
                  失败
                </span>
                <span
                  v-else
                  class="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                  <FileTextOutlined />
                  已保存
                </span>
              </div>

              <div
                v-if="note.status === 'pending'"
                class="mt-3 h-4 w-2/3 animate-pulse rounded-full bg-zinc-200"></div>
              <div
                v-else
                class="mt-3 truncate text-sm font-semibold text-zinc-900">
                {{ note.title || note.query || '未命名笔记' }}
              </div>

              <div class="mt-2 text-xs leading-5 text-zinc-500 line-clamp-2">
                {{ note.answer_excerpt || note.query }}
              </div>
              <div
                v-if="note.status === 'failed' && note.last_error"
                class="mt-2 text-xs leading-5 text-red-600 line-clamp-2">
                {{ note.last_error }}
              </div>
            </div>
          </div>
        </button>
      </section>
    </div>
  </section>
</template>
