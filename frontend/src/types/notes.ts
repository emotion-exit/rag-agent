export interface NoteSourceSummary {
  index: number;
  doc_id: string;
  filename: string;
  chunk_index: number;
  knowledge_space: string;
  tags: string;
  source_type: string;
  source_label: string;
  source_page: number;
  section_title?: string;
  heading_path?: string;
  image_count?: number;
  summary: string;
}

export interface NoteListItem {
  note_id: string;
  session_id: string;
  message_id: string;
  knowledge_space: string;
  query: string;
  answer_excerpt: string;
  title: string;
  status: 'pending' | 'ready' | 'failed';
  current_revision_id: string;
  last_error: string;
  created_at: string;
  updated_at: string;
}

export interface NoteSaveJob {
  job_id: string;
  note_id: string;
  status: 'pending' | 'running' | 'succeeded' | 'failed';
  error_message: string;
  created_at: string;
  updated_at: string;
  completed_at: string;
}

export interface NoteRevision {
  revision_id: string;
  query: string;
  answer: string;
  title: string;
  created_at: string;
}

export interface NoteDetail {
  note: NoteListItem;
  current_revision: NoteRevision | null;
  sources: NoteSourceSummary[];
}

export interface NoteRevisionDraft {
  query: string;
  answer: string;
  sources: NoteSourceSummary[];
  generated_at: string;
}

export interface CreateNoteSaveJobInput {
  session_id: string;
  message_id: string;
  query: string;
  answer: string;
  knowledge_space: string;
  sources: NoteSourceSummary[];
}

export interface CreateNoteRevisionSaveJobInput {
  answer: string;
  sources: NoteSourceSummary[];
}
