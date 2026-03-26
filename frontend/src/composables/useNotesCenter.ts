import { computed, onBeforeUnmount, reactive, ref, type Ref } from 'vue';
import type { OToastApi } from '@/orange-ui';
import {
  createNoteRevisionSaveJob,
  createNoteSaveJob,
  fetchNoteDetail,
  fetchNoteSaveJob,
  fetchNotes,
  generateNoteRevisionDraft
} from '@/services/notes';
import type {
  NoteDetail,
  NoteListItem,
  NoteRevisionDraft
} from '@/types/notes';
import type { Message } from '@/components/AnswerCard.vue';

interface UseNotesCenterOptions {
  sessionId: Ref<string>;
  sessionKnowledgeSpaceLabel: Ref<string>;
  toast: OToastApi;
}

export function useNotesCenter(options: UseNotesCenterOptions) {
  const { sessionId, sessionKnowledgeSpaceLabel, toast } = options;

  const notesVisible = ref(false);
  const notes = ref<NoteListItem[]>([]);
  const notesLoading = ref(false);
  const selectedNoteId = ref('');
  const selectedNoteDetail = ref<NoteDetail | null>(null);
  const noteDetailLoading = ref(false);
  const revisionDraft = ref<NoteRevisionDraft | null>(null);
  const revisionDraftLoading = ref(false);
  const savingMessageId = ref('');
  const noteJobsByMessageId = reactive<Record<string, string>>({});
  const noteRevisionJobsByNoteId = reactive<Record<string, string>>({});
  let notePollingTimer: number | null = null;

  const notesByKnowledgeSpace = computed(() => {
    const grouped = new Map<string, NoteListItem[]>();

    for (const note of notes.value) {
      const groupKey =
        String(note.knowledge_space || '').trim() || '未指定知识库';
      const current = grouped.get(groupKey) || [];
      current.push(note);
      grouped.set(groupKey, current);
    }

    return Array.from(grouped.entries()).map(([knowledgeSpace, items]) => ({
      knowledgeSpace,
      items
    }));
  });

  function getSelectedNote(noteId = selectedNoteId.value) {
    return notes.value.find((item) => item.note_id === noteId) || null;
  }

  function isMessageNoteSaving(messageId: string) {
    return Boolean(noteJobsByMessageId[messageId]);
  }

  function isNoteRevisionSaving(noteId: string) {
    return Boolean(noteRevisionJobsByNoteId[noteId]);
  }

  function stopNotePolling() {
    if (notePollingTimer !== null) {
      window.clearInterval(notePollingTimer);
      notePollingTimer = null;
    }
  }

  function ensureNotePolling() {
    if (notePollingTimer !== null) {
      return;
    }

    notePollingTimer = window.setInterval(() => {
      void pollNoteJobs();
    }, 1500);
  }

  async function loadNotes(options: { silent?: boolean } = {}) {
    const { silent = false } = options;
    if (!silent) {
      notesLoading.value = true;
    }

    try {
      const items = await fetchNotes();
      notes.value = items;

      if (!selectedNoteId.value && items.length > 0) {
        const firstReady =
          items.find((item) => item.status === 'ready') || items[0];
        if (firstReady) {
          selectedNoteId.value = firstReady.note_id;
        }
      }

      if (
        selectedNoteId.value &&
        !items.some((item) => item.note_id === selectedNoteId.value)
      ) {
        selectedNoteId.value = '';
        selectedNoteDetail.value = null;
      }
    } finally {
      if (!silent) {
        notesLoading.value = false;
      }
    }
  }

  async function loadNoteDetail(
    noteId: string,
    options: { silent?: boolean } = {}
  ) {
    const { silent = false } = options;
    if (selectedNoteId.value !== noteId) {
      revisionDraft.value = null;
    }
    selectedNoteId.value = noteId;

    const selectedNote = getSelectedNote(noteId);
    if (selectedNote?.status !== 'ready') {
      selectedNoteDetail.value = null;
      revisionDraft.value = null;
      noteDetailLoading.value = false;
      return;
    }

    if (!silent) {
      noteDetailLoading.value = true;
    }

    try {
      selectedNoteDetail.value = await fetchNoteDetail(noteId);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '笔记详情加载失败');
    } finally {
      noteDetailLoading.value = false;
    }
  }

  async function pollNoteJobs() {
    const messageEntries = Object.entries(noteJobsByMessageId);
    const revisionEntries = Object.entries(noteRevisionJobsByNoteId);
    if (messageEntries.length === 0 && revisionEntries.length === 0) {
      stopNotePolling();
      return;
    }

    let shouldRefreshNotes = false;

    for (const [messageId, jobId] of messageEntries) {
      try {
        const job = await fetchNoteSaveJob(jobId);
        if (job.status === 'succeeded') {
          delete noteJobsByMessageId[messageId];
          if (savingMessageId.value === messageId) {
            savingMessageId.value = '';
          }
          shouldRefreshNotes = true;
        } else if (job.status === 'failed') {
          delete noteJobsByMessageId[messageId];
          if (savingMessageId.value === messageId) {
            savingMessageId.value = '';
          }
          shouldRefreshNotes = true;
          toast.error(job.error_message || '笔记保存失败');
        }
      } catch (error) {
        delete noteJobsByMessageId[messageId];
        if (savingMessageId.value === messageId) {
          savingMessageId.value = '';
        }
        shouldRefreshNotes = true;
        toast.error(
          error instanceof Error ? error.message : '笔记状态获取失败'
        );
      }
    }

    for (const [noteId, jobId] of revisionEntries) {
      try {
        const job = await fetchNoteSaveJob(jobId);
        if (job.status === 'succeeded') {
          delete noteRevisionJobsByNoteId[noteId];
          shouldRefreshNotes = true;
          toast.success('笔记已更新');
        } else if (job.status === 'failed') {
          delete noteRevisionJobsByNoteId[noteId];
          shouldRefreshNotes = true;
          toast.error(job.error_message || '笔记版本保存失败');
        }
      } catch (error) {
        delete noteRevisionJobsByNoteId[noteId];
        shouldRefreshNotes = true;
        toast.error(
          error instanceof Error ? error.message : '笔记状态获取失败'
        );
      }
    }

    if (shouldRefreshNotes) {
      await loadNotes({ silent: true });
      const selectedNote = getSelectedNote();
      if (selectedNoteId.value && selectedNote?.status === 'ready') {
        await loadNoteDetail(selectedNoteId.value, { silent: true });
      }
    }

    if (
      Object.keys(noteJobsByMessageId).length === 0 &&
      Object.keys(noteRevisionJobsByNoteId).length === 0
    ) {
      stopNotePolling();
    }
  }

  async function openNotesModal() {
    await loadNotes();
    notesVisible.value = true;
    const selectedNote = getSelectedNote();
    if (selectedNoteId.value && selectedNote?.status === 'ready') {
      await loadNoteDetail(selectedNoteId.value, { silent: true });
    }
  }

  function closeNotesModal() {
    notesVisible.value = false;
    revisionDraft.value = null;
  }

  function discardRevisionDraft() {
    revisionDraft.value = null;
  }

  async function generateSelectedNoteRevisionDraft() {
    const selectedNote = getSelectedNote();
    if (!selectedNote || selectedNote.status !== 'ready') {
      return;
    }

    revisionDraftLoading.value = true;
    try {
      const draft = await generateNoteRevisionDraft({
        session_id: `note-revision-${selectedNote.note_id}-${Date.now()}`,
        query: selectedNote.query,
        knowledge_space: selectedNote.knowledge_space
      });
      if (!draft.answer) {
        throw new Error('候选答案为空');
      }
      revisionDraft.value = draft;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '候选更新生成失败');
    } finally {
      revisionDraftLoading.value = false;
    }
  }

  async function saveSelectedRevisionDraft() {
    const noteId = selectedNoteId.value;
    if (!noteId || !revisionDraft.value || isNoteRevisionSaving(noteId)) {
      return;
    }

    try {
      const result = await createNoteRevisionSaveJob(noteId, {
        answer: revisionDraft.value.answer,
        sources: revisionDraft.value.sources
      });
      noteRevisionJobsByNoteId[noteId] = result.job.job_id;
      revisionDraft.value = null;
      ensureNotePolling();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '版本保存失败');
    }
  }

  async function handleSaveNote(message: Message) {
    if (isMessageNoteSaving(message.id)) {
      return;
    }

    const query = String(message.queryText || '').trim();
    const answer = String(
      message.answerContent || message.content || ''
    ).trim();
    if (!query || !answer) {
      toast.error('当前回答缺少可保存的内容');
      return;
    }

    try {
      savingMessageId.value = message.id;
      const result = await createNoteSaveJob({
        session_id: sessionId.value,
        message_id: message.id,
        query,
        answer,
        knowledge_space: String(
          message.knowledgeSpaceLabel || sessionKnowledgeSpaceLabel.value || ''
        ).trim(),
        sources: (message.sources || []).map((source) => ({
          ...source,
          section_title: source.section_title || '',
          heading_path: source.heading_path || '',
          image_count: source.image_count || 0
        }))
      });

      noteJobsByMessageId[message.id] = result.job.job_id;
      notes.value = [
        result.note,
        ...notes.value.filter((item) => item.note_id !== result.note.note_id)
      ];
      ensureNotePolling();
    } catch (error) {
      if (savingMessageId.value === message.id) {
        savingMessageId.value = '';
      }
      toast.error(error instanceof Error ? error.message : '笔记保存失败');
    }
  }

  onBeforeUnmount(() => {
    stopNotePolling();
  });

  return {
    notesVisible,
    notes,
    notesByKnowledgeSpace,
    notesLoading,
    selectedNoteId,
    selectedNoteDetail,
    noteDetailLoading,
    revisionDraft,
    revisionDraftLoading,
    savingMessageId,
    isMessageNoteSaving,
    isNoteRevisionSaving,
    loadNotes,
    loadNoteDetail,
    openNotesModal,
    closeNotesModal,
    handleSaveNote,
    discardRevisionDraft,
    generateSelectedNoteRevisionDraft,
    saveSelectedRevisionDraft
  };
}
