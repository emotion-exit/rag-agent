import { getApiBase } from '@/services/runtime';
import { buildPublicConfigHeaders } from '@/services/publicConfig';
import type {
  CreateNoteRevisionSaveJobInput,
  CreateNoteSaveJobInput,
  NoteDetail,
  NoteListItem,
  NoteRevisionDraft,
  NoteSaveJob,
  NoteSourceSummary
} from '@/types/notes';

interface NoteListResponse {
  items: NoteListItem[];
}

interface NoteJobResponse {
  job: NoteSaveJob;
}

interface CreateNoteJobResponse {
  success: boolean;
  job: NoteSaveJob;
  note: NoteListItem;
}

interface ChatResponse {
  reply: string;
  sources: NoteSourceSummary[];
}

async function parseApiError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return String(payload.detail || '').trim() || `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

export async function fetchNotes(): Promise<NoteListItem[]> {
  const response = await fetch(`${getApiBase()}/api/notes`, {
    headers: buildPublicConfigHeaders()
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const payload = (await response.json()) as NoteListResponse;
  return Array.isArray(payload.items) ? payload.items : [];
}

export async function fetchNoteDetail(noteId: string): Promise<NoteDetail> {
  const response = await fetch(
    `${getApiBase()}/api/notes/${encodeURIComponent(noteId)}`,
    {
      headers: buildPublicConfigHeaders()
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as NoteDetail;
}

export async function createNoteSaveJob(
  payload: CreateNoteSaveJobInput
): Promise<CreateNoteJobResponse> {
  const response = await fetch(`${getApiBase()}/api/notes/save-jobs`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...buildPublicConfigHeaders()
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as CreateNoteJobResponse;
}

export async function fetchNoteSaveJob(jobId: string): Promise<NoteSaveJob> {
  const response = await fetch(
    `${getApiBase()}/api/notes/save-jobs/${encodeURIComponent(jobId)}`,
    {
      headers: buildPublicConfigHeaders()
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const payload = (await response.json()) as NoteJobResponse;
  return payload.job;
}

export async function generateNoteRevisionDraft(input: {
  session_id: string;
  query: string;
  knowledge_space: string;
}): Promise<NoteRevisionDraft> {
  const retrievalFilters = input.knowledge_space.trim()
    ? { knowledge_space: input.knowledge_space.trim() }
    : undefined;

  const response = await fetch(`${getApiBase()}/api/chat/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...buildPublicConfigHeaders()
    },
    body: JSON.stringify({
      message: input.query,
      session_id: input.session_id,
      retrieval_filters: retrievalFilters
    })
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const payload = (await response.json()) as ChatResponse;
  return {
    query: input.query,
    answer: String(payload.reply || '').trim(),
    sources: Array.isArray(payload.sources) ? payload.sources : [],
    generated_at: new Date().toISOString()
  };
}

export async function createNoteRevisionSaveJob(
  noteId: string,
  payload: CreateNoteRevisionSaveJobInput
): Promise<NoteJobResponse> {
  const response = await fetch(
    `${getApiBase()}/api/notes/${encodeURIComponent(noteId)}/revision-save-jobs`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...buildPublicConfigHeaders()
      },
      body: JSON.stringify(payload)
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as NoteJobResponse;
}
