import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { Artifact } from '../types'

const KIND_LABEL: Record<string, string> = {
  figure: '图', csv: '表格', pdf: 'PDF', html: '报告', h5ad: 'h5ad',
  log: '日志', report: '报告', bam: 'BAM', other: '文件',
}

export default function ArtifactGallery({ projectId }: { projectId: string }) {
  const [arts, setArts] = useState<Artifact[]>([])
  const [filter, setFilter] = useState('all')

  const refresh = useCallback(() => {
    api.artifacts(projectId).then(setArts).catch(console.error)
  }, [projectId])

  useEffect(refresh, [refresh])

  const kinds = Array.from(new Set(arts.map((a) => a.kind)))
  const shown = filter === 'all' ? arts : arts.filter((a) => a.kind === filter)

  return (
    <div>
      <div className="flex" style={{ marginBottom: 12 }}>
        <span className="muted">共 {arts.length} 个产物 · 由 Analysis Event 产生（不会出现「这张图是哪次分析生成的」问题）</span>
        <span className="spacer" style={{ flex: 1 }} />
        <button className="primary" onClick={() => window.open(`/api/projects/${projectId}/report`, '_blank')}>
          生成分析报告
        </button>
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">全部</option>
          {kinds.map((k) => <option key={k} value={k}>{KIND_LABEL[k] ?? k}</option>)}
        </select>
        <button onClick={refresh}>刷新</button>
      </div>

      <div className="artifact-grid">
        {shown.map((a) => (
          <div key={a.id} className="artifact-card">
            {a.kind === 'figure' && (
              <a href={api.artifactUrl(a.id)} target="_blank" rel="noreferrer">
                <img src={api.artifactUrl(a.id)} alt={a.name} loading="lazy" />
              </a>
            )}
            {a.kind === 'report' && <iframe src={api.artifactUrl(a.id)} title={a.name} sandbox="" />}
            <div className="info">
              <div className="name">{a.name}</div>
              <div className="flex" style={{ marginTop: 6 }}>
                <span className="badge gray">{KIND_LABEL[a.kind] ?? a.kind}</span>
                <span className="muted">{(a.size_bytes / 1024).toFixed(1)} KB</span>
                <span className="spacer" style={{ flex: 1 }} />
                <a href={api.artifactUrl(a.id)} target="_blank" rel="noreferrer">打开</a>
              </div>
              <div className="muted mono" style={{ marginTop: 4 }}>ev: {a.event_id.slice(0, 14)}</div>
            </div>
          </div>
        ))}
        {shown.length === 0 && <div className="empty">暂无产物。</div>}
      </div>
    </div>
  )
}
