import type { AgentStatus, Conversation, Environment, Project } from '../types'

const PHASE_LABEL: Record<string, string> = {
  raw: '原始数据', qc: '质控', normalized: '标准化', pca: 'PCA', neighbors: '邻接图',
  umap: 'UMAP', clustered: '聚类', annotated: '注释', marker_genes: '标记基因',
  de: '差异表达', aligned: '已比对',
}

export default function TopBar({
  project, conversation, environments, agentStatus, onSwitchEnv, onOpenSettings, onRefresh,
}: {
  project?: Project
  conversation?: Conversation
  environments: Environment[]
  agentStatus?: AgentStatus
  onSwitchEnv: (envId: string) => void
  onOpenSettings: () => void
  onRefresh: () => void
}) {
  const phase = conversation?.current_phase ?? 'raw'
  const phaseLabel = PHASE_LABEL[phase] ?? phase
  const agentLabel = agentStatus
    ? agentStatus.mode === 'real'
      ? `Agent · LLM (${agentStatus.model})`
      : agentStatus.mode === 'echo'
        ? 'Agent · LLM(echo)'
        : 'Agent · 规则引擎'
    : ''

  return (
    <div className="topbar">
      <span className="brand">
        <span className="logo" />
        <span className="title">BioAgent</span>
      </span>
      <span className="subtitle">生信分析工作台</span>
      <span className="spacer" />

      {project && (
        <>
          <span className="muted">项目</span>
          <span style={{ fontWeight: 500 }}>{project.name}</span>
          <span className="badge gray">阶段 {phaseLabel}</span>
        </>
      )}

      {agentStatus && <span className="badge blue">{agentLabel}</span>}

      <select
        value={conversation?.active_environment_id ?? ''}
        onChange={(e) => onSwitchEnv(e.target.value)}
        title="计算环境"
      >
        <option value="">计算环境：未指定</option>
        {environments.map((e) => (
          <option key={e.id} value={e.id}>
            {e.env_type === 'remote' ? '远程' : '本地'} · {e.name}
          </option>
        ))}
      </select>

      <button className="ghost" onClick={onRefresh} title="刷新">刷新</button>
      <button onClick={onOpenSettings} title="工作模式 / Agent / 环境 / API">设置</button>
    </div>
  )
}
