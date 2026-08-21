import { useEffect, useState } from 'react'
import { api } from '../api'
import type { AnalysisEvent, Diagnosis } from '../types'

const CAP_LABEL: Record<string, string> = {
  'scrna.inspect': '数据检查', 'scrna.qc': '细胞 QC', 'scrna.normalization': '标准化',
  'scrna.hvg': '高变基因', 'scrna.pca': 'PCA', 'scrna.neighbors': '邻接图',
  'scrna.umap': 'UMAP', 'scrna.clustering': '聚类', 'scrna.marker_genes': '标记基因',
  'scrna.annotation': '细胞注释',
  'bulk_rna.inspect': '数据检查', 'bulk_rna.qc': 'QC', 'bulk_rna.normalization': '标准化',
  'bulk_rna.differential_expression': '差异表达', 'bulk_rna.volcano': '火山图',
  'bulk_rna.heatmap': '热图', 'bulk_rna.go_enrichment': 'GO 富集', 'bulk_rna.gsea': 'GSEA',
  'bulk_rna.alignment': '序列比对',
}

export default function EventDetail({ eventId, onClose, onChanged }: {
  eventId: string
  onClose: () => void
  onChanged?: () => void
}) {
  const [ev, setEv] = useState<AnalysisEvent | null>(null)
  const [logs, setLogs] = useState('')
  const [showLogs, setShowLogs] = useState(false)
  const [diagnosis, setDiagnosis] = useState<Diagnosis | null>(null)
  const [showDiagnosis, setShowDiagnosis] = useState(false)
  const [diagnosing, setDiagnosing] = useState(false)
  const [rerunning, setRerunning] = useState(false)

  useEffect(() => {
    setEv(null)
    setShowLogs(false)
    setLogs('')
    setDiagnosis(null)
    api.event(eventId).then(setEv).catch(console.error)
  }, [eventId])

  const loadLogs = async () => {
    const next = !showLogs
    setShowLogs(next)
    if (next) {
      const r = await api.eventLogs(eventId)
      setLogs(r.logs)
    }
  }

  const diagnose = async () => {
    setDiagnosing(true)
    try {
      const d = await api.diagnoseEvent(eventId)
      setDiagnosis(d)
      setShowDiagnosis(true)
    } catch (e) { alert((e as Error).message) } finally { setDiagnosing(false) }
  }

  const rerunWithSuggested = async () => {
    if (!diagnosis) return
    setRerunning(true)
    try {
      await api.rerunEvent(eventId, diagnosis.suggested_params)
      alert('已用建议参数重跑，新事件挂到 DAG（re_run 边）。')
      onChanged?.()
    } catch (e) { alert((e as Error).message) } finally { setRerunning(false) }
  }

  if (!ev) return <div className="empty">加载事件…</div>

  return (
    <div className="event-detail">
      <div className="flex" style={{ marginBottom: 8 }}>
        <span style={{ fontWeight: 600 }}>{CAP_LABEL[ev.capability_id] ?? ev.capability_id}</span>
        <span className={`badge ${ev.status === 'succeeded' ? 'green' : ev.status === 'failed' ? 'red' : 'amber'}`}>
          {ev.status}
        </span>
        <span className="muted mono">{ev.id}</span>
        <span className="spacer" />
        <button onClick={loadLogs}>{showLogs ? '收起日志' : '查看日志'}</button>
        <button onClick={onClose}>关闭</button>
      </div>

      {ev.error && (
        <div className="card" style={{ background: 'var(--red-soft)', borderColor: 'var(--red)', marginBottom: 10 }}>
          <div className="flex" style={{ alignItems: 'flex-start' }}>
            <div style={{ flex: 1 }}>
              <b style={{ color: 'var(--red)' }}>执行失败：{ev.error.message}</b>
              {ev.error.stage && <div className="muted">stage: {ev.error.stage} · type: {ev.error.type}</div>}
            </div>
            <button onClick={diagnose} disabled={diagnosing}>
              {diagnosing ? '诊断中…' : '诊断原因'}
            </button>
          </div>
          {showDiagnosis && diagnosis && (
            <div style={{ marginTop: 10, background: 'var(--panel)', borderRadius: 8, padding: 10 }}>
              <div style={{ marginBottom: 6 }}>{diagnosis.message}</div>
              {Object.keys(diagnosis.suggested_params).length > 0 && (
                <div className="mono muted" style={{ marginBottom: 8 }}>
                  建议参数：{JSON.stringify(diagnosis.suggested_params)}
                </div>
              )}
              {Object.keys(diagnosis.suggested_params).length > 0 && (
                <button className="primary" onClick={rerunWithSuggested} disabled={rerunning}>
                  {rerunning ? '重跑中…' : '用建议参数重跑'}
                </button>
              )}
            </div>
          )}
        </div>
      )}

      <div className="detail-grid">
        <div>
          <div className="kv"><span className="k">实现</span><span className="mono">{ev.implementation}{ev.runtime_id ? ` @ ${ev.runtime_id}` : ''}</span></div>
          <div className="kv"><span className="k">输入数据集</span><span className="mono">{(ev.inputs.dataset as string) ?? '—'}</span></div>
          <div className="kv"><span className="k">参数</span><span className="mono">{JSON.stringify(ev.parameters)}</span></div>
          <div className="kv"><span className="k">执行模式</span><span className="mono">{String(ev.metrics.executor_mode ?? '—')}</span></div>
          {Object.entries(ev.metrics).filter(([k]) => k !== 'executor_mode').map(([k, v]) => (
            <div className="kv" key={k}><span className="k">{k}</span><span className="mono">{String(v)}</span></div>
          ))}
        </div>
        <div>
          <div className="muted" style={{ marginBottom: 4 }}>产物（{ev.artifacts.length}）</div>
          {ev.artifacts.map((a) => (
            <div className="kv" key={a.id}>
              <span className="badge gray">{a.kind}</span>
              <a href={api.artifactUrl(a.id)} target="_blank" rel="noreferrer">{a.name}</a>
            </div>
          ))}
          {ev.artifacts.length === 0 && <div className="muted">无产物</div>}
        </div>
      </div>

      {showLogs && (
        <div style={{ marginTop: 10 }}>
          <pre className="logs">{logs || '（无日志）'}</pre>
        </div>
      )}
    </div>
  )
}
