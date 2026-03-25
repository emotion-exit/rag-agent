export interface DocumentInfo {
  doc_id: string;
  filename: string;
  chunk_count: number;
  upload_time: string;
  knowledge_space: string;
  tags: string;
  image_count: number;
  space_id: string;
  visibility: 'public' | 'private';
  owner_id: string;
}

export interface KnowledgeSpace {
  space_id: string;
  name: string;
  tags: string;
  description: string;
  owner_id: string;
  visibility: 'public' | 'private';
  created_at: string;
  updated_at: string;
  document_count: number;
}

export interface Stats {
  total_chunks: number;
  total_documents: number;
}

export interface SpaceSummary {
  total_spaces: number;
  total_documents: number;
  ungrouped_documents: number;
}

export interface KnowledgeSpaceCreateForm {
  name: string;
  tags: string;
  description: string;
  visibility: 'public' | 'private';
}

export interface UploadForm {
  tags: string;
}

export interface UploadSubmitPayload extends UploadForm {
  files: File[];
}

export type KnowledgeBaseJobType = 'upload';

export type KnowledgeBaseJobStatusValue =
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed';

export interface KnowledgeBaseJobStatus {
  job_id: string;
  job_type: KnowledgeBaseJobType;
  status: KnowledgeBaseJobStatusValue;
  message: string;
  error_message: string;
  current_document: string;
  total_documents: number;
  processed_documents: number;
  total_chunks: number;
  processed_chunks: number;
  created_at: string;
  updated_at: string;
  result?: Record<string, unknown>;
}
