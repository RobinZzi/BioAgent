// API 封装（fetch）
import type {
  AgentStatus, AnalysisEvent, Artifact, Capability, Conversation, ConversationDetail,
  Dag, Dataset, Diagnosis, Environment, MessageResult, Project, ProjectDetail,
  ResolveResult, RStudioHandoff, RStudioImportResult, Settings,
} from './types'

const BASE = '/api'

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('bioagent_token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(BASE + path, { headers, ...options })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  // auth
  register: (username: string, password: string) =>
    req<{ token: string; username: string; is_admin: boolean }>('/auth/register', { method: 'POST', body: JSON.stringify({ username, password }) }),
  login: (username: string, password: string) =>
    req<{ token: string; username: string; is_admin: boolean }>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  me: () => req<{ username: string; is_admin: boolean }>('/auth/me'),
  logout: () => localStorage.removeItem('bioagent_token'),

  // projects
  listProjects: () => req<Project[]>('/projects'),
  createProject: (body: { name: string; description?: string; data_source?: string; compute_location?: string; workdir?: string; server_id?: string }) =>
    req<Project>('/projects', { method: 'POST', body: JSON.stringify(body) }),
  patchProject: (id: string, body: { name?: string; workdir?: string }) =>
    req<Project>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  fsList: (path: string) => req<{ path: string; parent: string; dirs: string[] }>(`/fs/list?path=${encodeURIComponent(path)}`),
  servers: () => req<Environment[]>('/servers'),
  batchDeleteProjects: (projectIds: string[], deleteFiles: boolean) =>
    req<{ deleted: string[]; deleted_files: boolean }>('/projects/batch-delete', {
      method: 'POST', body: JSON.stringify({ project_ids: projectIds, delete_files: deleteFiles }),
    }),
  projectDetail: (id: string) => req<ProjectDetail>(`/projects/${id}`),

  // conversations
  createConversation: (projectId: string) =>
    req<Conversation>(`/projects/${projectId}/conversations`, { method: 'POST' }),
  conversationDetail: (id: string) => req<ConversationDetail>(`/conversations/${id}`),
  sendMessage: (id: string, content: string, wait: boolean) =>
    req<MessageResult>(`/conversations/${id}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content, wait }),
    }),

  // datasets
  registerDataset: (projectId: string, body: { name: string; dtype?: string; format?: string; location?: string; phase?: string; metadata?: Record<string, unknown> }) =>
    req<Dataset>(`/projects/${projectId}/datasets`, { method: 'POST', body: JSON.stringify(body) }),
  patchDataset: (id: string, body: { name?: string; tags?: string[] }) =>
    req<Dataset>(`/datasets/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteDataset: (id: string) => req<{ deleted: string }>(`/datasets/${id}`, { method: 'DELETE' }),
  projectFiles: (projectId: string, path: string) =>
    req<{ path: string; is_dir: boolean; dirs: string[]; files: { name: string; size: number }[] }>(`/projects/${projectId}/files?path=${encodeURIComponent(path)}`),

  // environments
  discoverEnvironment: (projectId: string) =>
    req<Environment>(`/projects/${projectId}/environments/discover`, { method: 'POST' }),
  rediscoverEnvironment: (envId: string) =>
    req<Environment>(`/environments/${envId}/rediscover`, { method: 'POST' }),
  registerRemoteEnvironment: (projectId: string, body: { name: string; connector_url: string; token: string }) =>
    req<Environment>(`/projects/${projectId}/environments/register-remote`, { method: 'POST', body: JSON.stringify(body) }),
  registerRemoteGlobal: (body: { name: string; connector_url: string; token: string }) =>
    req<Environment>('/environments/register-remote', { method: 'POST', body: JSON.stringify(body) }),
  registerSSHEnvironment: (projectId: string, body: { name: string; host: string; port: number; user: string; password: string; key_path: string }) =>
    req<Environment>(`/projects/${projectId}/environments/register-ssh`, { method: 'POST', body: JSON.stringify(body) }),
  registerSSHGlobal: (body: { name: string; host: string; port: number; user: string; password: string; key_path: string }) =>
    req<Environment>('/environments/register-ssh', { method: 'POST', body: JSON.stringify(body) }),
  testEnvironment: (envId: string) =>
    req<{ ok: boolean; detail: string; env_type: string }>(`/environments/${envId}/test`, { method: 'POST' }),
  setConversationEnvironment: (convId: string, environmentId: string) =>
    req<Conversation>(`/conversations/${convId}/set-environment`, { method: 'POST', body: JSON.stringify({ environment_id: environmentId }) }),

  // agent
  agentStatus: () => req<AgentStatus>('/agent/status'),

  // settings
  settings: () => req<Settings>('/settings'),
  patchSettings: (body: { executor_mode?: string; llm_mode?: string; llm_api_key?: string; llm_base_url?: string; llm_model?: string }) =>
    req<Settings>('/settings', { method: 'PATCH', body: JSON.stringify(body) }),

  // capabilities
  capabilities: () => req<Capability[]>('/capabilities'),
  resolve: (capabilityId: string, environmentId?: string) =>
    req<ResolveResult>(`/capabilities/resolve?capability_id=${encodeURIComponent(capabilityId)}${environmentId ? `&environment_id=${environmentId}` : ''}`),

  // events & dag
  dag: (projectId: string) => req<Dag>(`/projects/${projectId}/dag`),
  event: (id: string) => req<AnalysisEvent>(`/events/${id}`),
  eventLogs: (id: string) => req<{ event_id: string; logs: string }>(`/events/${id}/logs`),
  rerunEvent: (id: string, parameters: Record<string, unknown> = {}) =>
    req<AnalysisEvent>(`/events/${id}/rerun`, { method: 'POST', body: JSON.stringify({ parameters }) }),
  diagnoseEvent: (id: string) =>
    req<Diagnosis>(`/events/${id}/diagnose`, { method: 'POST' }),

  // rstudio manual handoff
  rstudioHandoff: (id: string) =>
    req<RStudioHandoff>(`/events/${id}/rstudio`, { method: 'POST' }),
  rstudioZipUrl: (id: string) => `${BASE}/events/${id}/rstudio/zip`,
  rstudioImport: (id: string, body: { output_dir?: string; name?: string; dtype?: string; phase?: string } = {}) =>
    req<RStudioImportResult>(`/events/${id}/rstudio/import`, { method: 'POST', body: JSON.stringify(body) }),

  // artifacts
  artifacts: (projectId: string) => req<Artifact[]>(`/projects/${projectId}/artifacts`),
  artifactUrl: (id: string) => `${BASE}/artifacts/${id}/content`,
}
