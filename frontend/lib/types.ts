export type SourceType = "document" | "internet" | "fallback";

export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  source?: SourceType;
  confidence?: number;
  createdAt: string;
}

export interface AskResponse {
  answer: string;
  source: SourceType;
  confidence: number;
  session_id?: string;
}

export interface KnowledgeDocument {
  document_id: string;
  file_name: string;
  source_type: string;
  created_at: string;
  chunk_count: number;
}

export interface StreamEvent {
  type: "status" | "meta" | "token" | "error" | "done";
  message?: string;
  source?: SourceType;
  confidence?: number;
  content?: string;
  session_id?: string;
}

export interface ToastItem {
  id: string;
  title: string;
  tone?: "info" | "success" | "error";
}
