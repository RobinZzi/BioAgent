import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { AgentStatus, ConversationDetail, ProjectDetail } from '../types'
import ConversationPanel from './ConversationPanel'
import AnalysisDAG from './AnalysisDAG'
import ArtifactGallery from './ArtifactGallery'
import DatasetChain from './DatasetChain'
import EnvironmentPanel from './EnvironmentPanel'

const PHASE_LABEL: Record<string, string> = {
  raw: '原始数据', qc: '质控', normalized: '标准化', pca: 'PCA', neighbors: '邻接图',
  umap: 'UMAP', clustered: '聚类', annotated: '注释', marker_genes: '标记基因',
  de: '差异表达', aligned: '已比对',
}

type Tab = 'dag' | 'datasets' | 'artifacts' | 'env'

export default function Workspace({ projectId, onBack }: { projectId: string; onBack: () => void }) {
  const [detail, setDetail] = useState<ProjectDetail | null>(null)
  const [conv, setConv] = useState<ConversationDetail | null>(null)
  const [tab, setTab] = useState<Tab>('dag')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null)
  const pollRef = useRef<number | null>(null)

  useEffect(() => {
    api.agentStatus().then(setAgentStatus).catch(() => {})
  }, [])

  const refresh = useCallback(async () => {
    try {
      const d = await api.projectDetail(projectId)
      setDetail(d)
      const convId = d.conversations[0]?.id
      if (convId) {
        const c = await api.conversationDetail(convId)
        setConv(c)
      }
      setError('')
    } catch (e) {
      setError((e as Error).message)
    }
  }, [projectId])

  useEffect(() => { refresh() }, [refresh])

  // 分析进行中轮询：直到最后一条助手消息不再是占位符
  useEffect(() => {
    if (!busy) return
    const started = Date.now()
    const timer = window.setInterval(async () => {
      try {
        const convId = detail?.conversations[0]?.id
        if (!convId) return
        const c = await api.conversationDetail(convId)
        setConv(c)
        const last = c.messages[c.messages.length - 1]
        const done = last && last.role === 'assistant' && !last.content.startsWith('⏳')
        if (done || Date.now() - started > 180000) {
          setBusy(false)
          refresh()
        }
      } catch { /* 网络抖动忽略 */ }
    }, 1500)
    pollRef.current = timer
    return () => window.clearInterval(timer)
  }, [busy, detail, refresh])

  if (!detail) {
    return <div className="empty">{error ? `加载失败：${error}` : '加载中…'}</div>
  }

  const convObj = conv?.conversation ?? detail.conversations[0]
  const phaseLabel = PHASE_LABEL[convObj?.current_phase ?? 'raw'] ?? convObj?.current_phase
  const stateSummary = convObj?.analysis_state?.summary

  const switchEnv = async (envId: string) => {
    if (!convObj?.id) return
    try {
      await api.setConversationEnvironment(convObj.id, envId)
      await refresh()
    } catch (e) { alert((e as Error).message) }
  }

  const agentBadge = agentStatus
    ? agentStatus.mode === 'real'
      ? { cls: 'green', label: `LLM · ${agentStatus.model}` }
      : agentStatus.mode === 'echo'
        ? { cls: 'amber', label: 'LLM(echo)' }
        : { cls: 'gray', label: '规则引擎' }
    : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="topbar">
        <button onClick={onBack}>← 项目列表</button>
        <h1>📁 {detail.project.name}</h1>
        <div className="context-chip" title="当前数据集（上下文指针）">
          <span className="muted">当前数据集</span>
          <span className="mono">{convObj?.current_dataset_id?.slice(0, 12) ?? '—'}</span>
        </div>
        <div className="context-chip" title="数据所处分析阶段">
          <span className="muted">阶段</span>
          <span className={`badge ${phaseLabel === '注释' ? 'green' : 'blue'}`}>{phaseLabel}</span>
        </div>
        {stateSummary && <div className="context-chip">{stateSummary}</div>}
        <div className="context-chip" title="Agent 大脑：规则引擎 / LLM（v0.2 可配置）">
          <span className="muted">Agent</span>
          {agentBadge && <span className={`badge ${agentBadge.cls}`}>{agentBadge.label}</span>}
        </div>
        <div className="context-chip" title="对话使用的计算环境">
          <span className="muted">环境</span>
          <select
            value={convObj?.active_environment_id ?? ''}
            onChange={(e) => switchEnv(e.target.value)}
            style={{ padding: '2px 6px', fontSize: 12, borderRadius: 6 }}
          >
            <option value="">（未指定）</option>
            {detail.environments.map((e) => (
              <option key={e.id} value={e.id}>
                {e.env_type === 'remote' ? '🔗' : '💻'} {e.name}
              </option>
            ))}
          </select>
        </div>
        <div className="spacer" />
        {busy && <span className="muted"><span className="spin">⏳</span> 分析执行中…</span>}
        <button onClick={refresh}>刷新</button>
      </div>

      <div className="workspace">
        <ConversationPanel
          convId={convObj?.id}
          messages={conv?.messages ?? []}
          busy={busy}
          onSendStart={() => setBusy(true)}
          onRefresh={refresh}
        />

        <div className="right-panel">
          <div className="tabs">
            {([['dag', '分析 DAG'], ['datasets', '数据集'], ['artifacts', '产物'], ['env', '环境 / 能力']] as [Tab, string][]).map(([k, label]) => (
              <button key={k} className={tab === k ? 'active' : ''} onClick={() => setTab(k)}>{label}</button>
            ))}
          </div>
          <div className="tab-body">
            {tab === 'dag' && <AnalysisDAG dag={detail.dag} onRefresh={refresh} />}
            {tab === 'datasets' && <DatasetChain datasets={detail.datasets} />}
            {tab === 'artifacts' && <ArtifactGallery projectId={projectId} />}
            {tab === 'env' && <EnvironmentPanel environments={detail.environments} projectId={projectId} onRefresh={refresh} />}
          </div>
        </div>
      </div>
    </div>
  )
}
