import { useEffect, useState } from 'react'
import { api } from '../api'
import type { AnalysisEvent } from '../types'

const CAP_LABEL: Record<string, string> = {
  'scrna.inspect': '数据检查', 'scrna.qc': '细胞 QC', 'scrna.normalization': '标准化',
  'scrna.hvg': '高变基因', 'scrna.pca': 'PCA', 'scrna.neighbors': '邻接图',
  'scrna.umap': 'UMAP', 'scrna.clustering': '聚类', 'scrna.marker_genes': '标记基因',
  'scrna.annotation': '细胞注释',
  'bulk_rna.inspect': '数据检查', 'bulk_rna.qc': 'QC', 'bulk_rna.normalization': '标准化',
  'bulk_rna.fastqc': 'FastQC', 'bulk_rna.trimming': '去接头裁切',
  'bulk_rna.alignment': '序列比对', 'bulk_rna.quantification': '基因定量',
  'bulk_rna.differential_expression': '差异表达', 'bulk_rna.volcano': '火山图',
  'bulk_rna.heatmap': '热图', 'bulk_rna.go_enrichment': 'GO 富集', 'bulk_rna.gsea': 'GSEA',
}

/** 分析历史对比视图：并排对比多个事件的参数 / 指标 / 产物，差异参数高亮。 */
export default function CompareView({ eventIds, onClose }: {
  eventIds: string[]
  onClose: () => void
}) {
  const [events, setEvents] = useState<AnalysisEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all(eventIds.map((id) => api.event(id).catch(() => null)))
      .then((list) => setEvents(list.filter(Boolean) as AnalysisEvent[]))
      .finally(() => setLoading(false))
  }, [eventIds.join(',')]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <div className="empty">加载对比数据…</div>
  if (events.length < 2) return <div className="empty">请至少选择两个事件进行对比。</div>

  // 参数差异分析
  const paramKeys = Array.from(new Set(events.flatMap((e) => Object.keys(e.parameters))))
  const diffParams = new Set<string>()
  for (const k of paramKeys) {
    const vals = new Set(events.map((e) => JSON.stringify(e.parameters[k])))
    if (vals.size > 1) diffParams.add(k)
  }

  const metricKeys = Array.from(new Set(events.flatMap((e) => Object.keys(e.metrics).filter((m) => m !== 'executor_mode'))))
  const diffMetrics = new Set<string>()
  for (const k of metricKeys) {
    const vals = new Set(events.map((e) => JSON.stringify(e.metrics[k])))
    if (vals.size > 1) diffMetrics.add(k)
  }

  const figures = events.map((e) => e.artifacts.filter((a) => a.kind === 'figure'))

  return (
    <div style={{ padding: '12px 14px', borderTop: '1px solid var(--border)' }}>
      <div className="flex" style={{ marginBottom: 10 }}>
        <b>参数对比</b>
        <span className="muted">（高亮 = 本次对比中的差异项）</span>
        <span className="spacer" />
        <button onClick={onClose}>关闭对比</button>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="kv-table">
          <thead>
            <tr>
              <th style={{ minWidth: 120 }}>事件</th>
              {events.map((e) => (
                <th key={e.id} style={{ minWidth: 180 }}>
                  {CAP_LABEL[e.capability_id] ?? e.capability_id}
                  <div className="muted mono" style={{ fontWeight: 400 }}>
                    {e.id.slice(0, 14)} · {e.status}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>执行模式</td>
              {events.map((e) => (
                <td key={e.id} className="mono">{String(e.metrics.executor_mode ?? '—')}</td>
              ))}
            </tr>
            {paramKeys.map((k) => (
              <tr key={k}>
                <td>{k}</td>
                {events.map((e) => {
                  const v = e.parameters[k]
                  return (
                    <td key={e.id} className="mono"
                        style={diffParams.has(k) ? { background: 'var(--amber-soft)', color: 'var(--amber)' } : undefined}>
                      {v === undefined ? '—' : JSON.stringify(v)}
                    </td>
                  )
                })}
              </tr>
            ))}
            {metricKeys.map((k) => (
              <tr key={k}>
                <td>{k}</td>
                {events.map((e) => (
                  <td key={e.id} className="mono"
                      style={diffMetrics.has(k) ? { background: 'var(--amber-soft)', color: 'var(--amber)' } : undefined}>
                    {e.metrics[k] === undefined ? '—' : String(e.metrics[k])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: 14 }}>
        <b>产物对比</b>
        <div className="artifact-grid" style={{ padding: '10px 0 0' }}>
          {events.map((e, i) => (
            <div key={e.id}>
              <div className="muted" style={{ marginBottom: 6 }}>
                {CAP_LABEL[e.capability_id] ?? e.capability_id}（{e.id.slice(0, 10)}）
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {figures[i].map((a) => (
                  <img key={a.id} src={api.artifactUrl(a.id)} alt={a.name}
                       style={{ width: '100%', border: '1px solid var(--border)', borderRadius: 4 }} />
                ))}
                {figures[i].length === 0 && <span className="muted">无图产物</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
