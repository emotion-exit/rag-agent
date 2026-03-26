<script setup lang="ts">
import { computed } from 'vue';
import { OModal } from '@/orange-ui';
import NoteDetailPanel from '@/components/notes/NoteDetailPanel.vue';
import NotesListPanel from '@/components/notes/NotesListPanel.vue';
import type {
  NoteDetail,
  NoteListItem,
  NoteRevisionDraft,
  NoteSourceSummary
} from '@/types/notes';

const props = defineProps<{
  visible: boolean;
  notesByKnowledgeSpace: Array<{
    knowledgeSpace: string;
    items: NoteListItem[];
  }>;
  notes: NoteListItem[];
  notesLoading: boolean;
  noteDetailLoading: boolean;
  selectedNoteId: string;
  selectedNoteDetail: NoteDetail | null;
  revisionDraft: NoteRevisionDraft | null;
  revisionDraftLoading: boolean;
  revisionSaving: boolean;
}>();

const emit = defineEmits<{
  close: [];
  refresh: [];
  selectNote: [noteId: string];
  openSource: [source: NoteSourceSummary];
  generateRevisionDraft: [];
  discardRevisionDraft: [];
  saveRevisionDraft: [];
}>();

const safeNotes = computed(() =>
  Array.isArray(props.notes) ? props.notes : []
);

const safeNoteGroups = computed(() =>
  Array.isArray(props.notesByKnowledgeSpace) ? props.notesByKnowledgeSpace : []
);

const selectedNoteSummary = computed(
  () =>
    safeNotes.value.find((item) => item.note_id === props.selectedNoteId) ||
    null
);

function requestRefresh() {
  emit('refresh');
}

function requestSelectNote(noteId: string) {
  emit('selectNote', noteId);
}

function requestOpenSource(source: NoteSourceSummary) {
  emit('openSource', source);
}
</script>

<template>
  <OModal
    :visible="visible"
    title="已保存笔记"
    subtitle="笔记保存采用异步任务执行，列表刷新不会影响当前聊天生成。"
    width="min(1120px, 100%)"
    cancel-text="关闭"
    @close="$emit('close')">
    <div class="grid gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
      <NotesListPanel
        :key="`notes-list-${safeNoteGroups.length}`"
        :note-groups="safeNoteGroups"
        :notes-loading="notesLoading"
        :selected-note-id="selectedNoteId"
        @refresh="requestRefresh"
        @select-note="requestSelectNote" />

      <NoteDetailPanel
        :key="`note-detail-${selectedNoteId || 'empty'}-${safeNotes.length}`"
        :note-detail-loading="noteDetailLoading"
        :selected-note-summary="selectedNoteSummary"
        :selected-note-detail="selectedNoteDetail"
        :revision-draft="revisionDraft"
        :revision-draft-loading="revisionDraftLoading"
        :revision-saving="revisionSaving"
        @generate-revision-draft="$emit('generateRevisionDraft')"
        @discard-revision-draft="$emit('discardRevisionDraft')"
        @save-revision-draft="$emit('saveRevisionDraft')"
        @open-source="requestOpenSource" />
    </div>
  </OModal>
</template>
