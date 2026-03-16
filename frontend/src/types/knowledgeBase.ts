export interface DocumentInfo {
  doc_id: string;
  filename: string;
  chunk_count: number;
  upload_time: string;
  knowledge_space: string;
  category: string;
  topic: string;
  tags: string;
  version_label: string;
  image_count: number;
  space_id: string;
  parent_space_id: string;
}

export interface KnowledgeSpace {
  space_id: string;
  name: string;
  parent_id: string;
  category: string;
  topic: string;
  tags: string;
  version_label: string;
  description: string;
  created_at: string;
  path: string;
  depth: number;
  child_count: number;
  direct_document_count: number;
  total_document_count: number;
  children?: KnowledgeSpace[];
}

export interface Stats {
  total_chunks: number;
  total_documents: number;
}

export interface SpaceSummary {
  total_spaces: number;
  ungrouped_documents: number;
}

export interface KnowledgeSpaceCreateForm {
  name: string;
  parent_id: string;
  category: string;
  topic: string;
  tags: string;
  version_label: string;
  description: string;
}

export interface UploadForm {
  tags: string;
  version_label: string;
}

export interface UploadSubmitPayload extends UploadForm {
  files: File[];
}

export type KnowledgeBaseJobType = 'upload' | 'migrate_ungrouped';

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
