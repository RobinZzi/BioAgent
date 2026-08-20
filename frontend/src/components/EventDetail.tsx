import { useEffect, useState } from 'react'
import { api } from '../api'
import type { AnalysisEvent } from '../types'

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

export default function EventDetail({ eventId, onClose }: {
  eventId: string
  onClose: () => void
}) {
  const [ev, setEv] = useState<AnalysisEvent | null>(null)
  const [logs, setLogs] = useState('')
  const [showLogs, setShowLogs] = useState(false)

  useEffect(() => {
    setEv(null)
    setShowLogs(false)
    setLogs('')
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
          <b style={{ color: 'var(--red)' }}>执行失败：{ev.error.message}</b>
          {ev.error.stage && <div className="muted">stage: {ev.error.stage} · type: {ev.error.type}</div>}
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
