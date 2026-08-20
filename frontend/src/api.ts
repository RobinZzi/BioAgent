// API 封装（fetch）
import type {
  AgentStatus, AnalysisEvent, Artifact, Capability, Conversation, ConversationDetail,
  Dag, Dataset, Environment, MessageResult, Project, ProjectDetail,
  ResolveResult, Settings,
} from './types'

const BASE = '/api'

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
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
  // projects
  listProjects: () => req<Project[]>('/projects'),
  createProject: (body: { name: string; description?: string; data_source?: string; compute_location?: string }) =>
    req<Project>('/projects', { method: 'POST', body: JSON.stringify(body) }),
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

  // environments
  discoverEnvironment: (projectId: string) =>
    req<Environment>(`/projects/${projectId}/environments/discover`, { method: 'POST' }),
  rediscoverEnvironment: (envId: string) =>
    req<Environment>(`/environments/${envId}/rediscover`, { method: 'POST' }),
  registerRemoteEnvironment: (projectId: string, body: { name: string; connector_url: string; token: string }) =>
    req<Environment>(`/projects/${projectId}/environments/register-remote`, { method: 'POST', body: JSON.stringify(body) }),
  registerSSHEnvironment: (projectId: string, body: { name: string; host: string; port: number; user: string; password: string; key_path: string }) =>
    req<Environment>(`/projects/${projectId}/environments/register-ssh`, { method: 'POST', body: JSON.stringify(body) }),
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

  // artifacts
  artifacts: (projectId: string) => req<Artifact[]>(`/projects/${projectId}/artifacts`),
  artifactUrl: (id: string) => `${BASE}/artifacts/${id}/content`,
}
