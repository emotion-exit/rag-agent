<script setup lang="ts">
import { computed } from 'vue';
import {
  ReloadOutlined,
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
    class="flex h-full min-h-0 flex-col rounded-2xl border border-zinc-200/60 bg-zinc-50/45 p-4">
    <div class="mb-4 flex items-center justify-between gap-3">
      <div class="text-xs font-bold uppercase tracking-[0.16em] text-zinc-500">
        笔记列表
      </div>
      <OButton
        variant="secondary"
        size="sm"
        class="h-8 w-8 rounded-full px-0 text-xs"
        :loading="notesLoading"
        @click="$emit('refresh')">
        <ReloadOutlined />
      </OButton>
    </div>

    <div v-if="notesLoading && safeNoteGroups.length === 0" class="space-y-3">
      <div
        v-for="index in 4"
        :key="`note-skeleton-${index}`"
        class="rounded-xl border border-zinc-200/60 bg-white/50 px-4 py-4">
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

    <div v-else class="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
      <section
        v-for="group in safeNoteGroups"
        :key="group.knowledgeSpace"
        class="space-y-2">
        <div
          class="sticky top-0 z-1 rounded-xl border border-zinc-200/80 bg-white/92 px-3 py-2 backdrop-blur-sm">
          <div
            class="truncate text-sm font-semibold tracking-tight text-zinc-900">
            {{ group.knowledgeSpace }}
          </div>
          <div
            class="mt-1 text-[11px] uppercase tracking-[0.14em] text-zinc-500">
            {{ group.items.length }} 条笔记
          </div>
        </div>

        <button
          v-for="note in group.items"
          :key="note.note_id"
          type="button"
          :class="[
            'w-full rounded-xl border px-3.5 py-3 text-left transition-all duration-200',
            selectedNoteId === note.note_id
              ? 'border-zinc-300 bg-white shadow-sm'
              : 'border-transparent bg-transparent hover:bg-white/70'
          ]"
          @click="$emit('selectNote', note.note_id)">
          <div class="flex items-start justify-between gap-2.5">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span
                  v-if="note.status === 'pending'"
                  class="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-600">
                  <LoadingOutlined class="animate-spin" />
                  保存中
                </span>
                <span
                  v-else-if="note.status === 'failed'"
                  class="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-red-700">
                  <WarningOutlined />
                  失败
                </span>
                <span
                  v-else
                  class="inline-flex h-2 w-2 rounded-full bg-emerald-500/80"></span>
                <span
                  v-if="note.status !== 'pending' && note.status !== 'failed'"
                  class="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">
                  已保存
                </span>
              </div>

              <div
                v-if="note.status === 'pending'"
                class="mt-3 h-4 w-2/3 animate-pulse rounded-full bg-zinc-200"></div>
              <div
                v-else
                class="mt-2 truncate text-sm font-semibold text-zinc-900">
                {{ note.title || note.query || '未命名笔记' }}
              </div>

              <div class="mt-1.5 text-xs leading-5 text-zinc-500 line-clamp-1">
                {{ note.answer_excerpt || note.query }}
              </div>
              <div
                v-if="note.status === 'failed' && note.last_error"
                class="mt-1.5 text-xs leading-5 text-red-600 line-clamp-2">
                {{ note.last_error }}
              </div>
            </div>
          </div>
        </button>
      </section>
    </div>
  </section>
</template>
