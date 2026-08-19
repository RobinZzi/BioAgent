// 与后端 API 对应的类型定义（见 backend/app/schemas.py）

export interface Project {
  id: string
  name: string
  description: string
  data_source: string
  compute_location: string
  created_at: string | null
  n_conversations: number
  n_datasets: number
  n_events: number
}

export interface Conversation {
  id: string
  project_id: string
  title: string
  current_dataset_id: string | null
  current_phase: string
  active_environment_id: string | null
  active_runtime_id: string | null
  analysis_state: Record<string, string>
  created_at: string | null
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  triggered_event_ids: string[]
  created_at: string | null
}

export interface Dataset {
  id: string
  name: string
  dtype: string
  format: string
  location: string
  phase: string
  parent_dataset_id: string | null
  source_event_id: string | null
  metadata: Record<string, unknown>
  created_at: string | null
}

export interface Environment {
  id: string
  project_id: string | null
  name: string
  env_type: string
  manifest: Record<string, unknown>
  status: string
  connector_url: string | null
  discovered_at: string | null
}

export interface AgentStatus {
  mode: 'off' | 'echo' | 'real'
  configured: boolean
  model: string | null
  base_url?: string
  description: string
}

export interface Artifact {
  id: string
  event_id: string
  kind: string
  name: string
  path: string
  mime: string
  size_bytes: number
  created_at: string | null
}

export interface AnalysisEvent {
  id: string
  project_id: string
  conversation_id: string | null
  message_id: string | null
  capability_id: string
  implementation: string
  runtime_id: string | null
  environment_id: string | null
  inputs: Record<string, unknown>
  parameters: Record<string, unknown>
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  error: { stage?: string; type?: string; message?: string; log_tail?: string[] } | null
  started_at: string | null
  finished_at: string | null
  output: { datasets?: string[]; artifacts?: string[] }
  metrics: Record<string, unknown>
  log_path: string | null
  artifacts: Artifact[]
  created_at: string | null
}

export interface DagNode {
  id: string
  capability_id: string
  implementation: string
  status: string
  parameters: Record<string, unknown>
  message_id: string | null
  output: { datasets?: string[]; artifacts?: string[] }
  error: { message?: string } | null
  created_at: string | null
}

export interface DagEdge {
  source: string
  target: string
  relation: string
}

export interface Dag {
  nodes: DagNode[]
  edges: DagEdge[]
  depth: Record<string, number>
}

export interface Capability {
  capability_id: string
  name: string
  domain: string
  dataset_dtype: string
  requires_phase: string
  resulting_phase: string | null
  produces_dataset: boolean
  parameters: Record<string, { type: string; default?: unknown; enum?: unknown[]; minimum?: number; maximum?: number; description?: string }>
  implementations: { id: string; language: string; runtime_hint: string; tools: string[]; default: boolean }[]
  description: string
  keywords: string[]
}

export interface ProjectDetail {
  project: Project
  conversations: Conversation[]
  datasets: Dataset[]
  environments: Environment[]
  dag: Dag
}

export interface ConversationDetail {
  conversation: Conversation
  messages: Message[]
  events: AnalysisEvent[]
}

export interface ResolveResult {
  capability_id: string
  implementations: { id: string; language: string; available: boolean; runtime_id: string | null; reason: string }[]
}

export interface MessageResult {
  user_message: Message
  assistant_message: Message
  events: AnalysisEvent[]
}
