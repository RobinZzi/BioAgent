import { useI18n } from '../i18n'
import type { AgentStatus, Conversation, Environment, Project } from '../types'

const PHASE_LABEL_ZH: Record<string, string> = {
  raw: '原始数据', qc: '质控', normalized: '标准化', pca: 'PCA', neighbors: '邻接图',
  umap: 'UMAP', clustered: '聚类', annotated: '注释', marker_genes: '标记基因',
  de: '差异表达', aligned: '已比对',
}
const PHASE_LABEL_EN: Record<string, string> = {
  raw: 'Raw', qc: 'QC', normalized: 'Normalized', pca: 'PCA', neighbors: 'Neighbors',
  umap: 'UMAP', clustered: 'Clustered', annotated: 'Annotated', marker_genes: 'Markers',
  de: 'DE', aligned: 'Aligned',
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
  const { lang, setLang, t } = useI18n()
  const phase = conversation?.current_phase ?? 'raw'
  const phaseLabel = (lang === 'en' ? PHASE_LABEL_EN : PHASE_LABEL_ZH)[phase] ?? phase
  const agentLabel = agentStatus
    ? agentStatus.mode === 'real'
      ? `Agent · LLM (${agentStatus.model})`
      : agentStatus.mode === 'echo'
        ? 'Agent · LLM(echo)'
        : `Agent · ${lang === 'en' ? 'Rules' : '规则引擎'}`
    : ''

  return (
    <div className="topbar">
      <span className="brand">
        <img src="/logo.svg" alt="BioAgent" className="logo-img" />
        <span className="title">BioAgent</span>
      </span>
      <span className="subtitle">{t('subtitle')}</span>
      <span className="spacer" />

      {project && (
        <>
          <span className="muted">{t('project')}</span>
          <span style={{ fontWeight: 500 }}>{project.name}</span>
          <span className="badge gray">{t('stage')} {phaseLabel}</span>
        </>
      )}

      {agentStatus && <span className="badge blue">{agentLabel}</span>}

      <select value={conversation?.active_environment_id ?? ''} onChange={(e) => onSwitchEnv(e.target.value)} title={t('env')}>
        <option value="">{t('env')}: {t('envNone')}</option>
        {environments.map((e) => (
          <option key={e.id} value={e.id}>
            {e.env_type === 'remote' ? t('remote') : t('local')} · {e.name}
          </option>
        ))}
      </select>

      <button className="ghost" style={{ padding: '2px 8px', fontSize: 12 }} onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')}>
        {lang === 'zh' ? 'EN' : '中'}
      </button>
      <button className="ghost" onClick={onRefresh} title={t('refresh')}>{t('refresh')}</button>
      <button onClick={onOpenSettings} title="Modes / Agent / Env / API">{t('settings')}</button>
    </div>
  )
}
