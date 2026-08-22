import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { Artifact } from '../types'
import { useI18n } from '../i18n'



export default function ArtifactGallery({ projectId }: { projectId: string }) {
  const { t } = useI18n()
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
        <span className="muted">{t('artifactCount')} {arts.length} · {t('artifactProvenance')}</span>
        <span className="spacer" style={{ flex: 1 }} />
        <button className="primary" onClick={() => window.open(`/api/projects/${projectId}/report`, '_blank')}>
          {t('generateReport')}
        </button>
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">{t("all")}</option>
          {kinds.map((k) => <option key={k} value={k}>{t(k)}</option>)}
        </select>
        <button onClick={refresh}>{t('refresh')}</button>
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
                <span className="badge gray">{t(a.kind)}</span>
                <span className="muted">{(a.size_bytes / 1024).toFixed(1)} KB</span>
                <span className="spacer" style={{ flex: 1 }} />
                <a href={api.artifactUrl(a.id)} target="_blank" rel="noreferrer">{t('open')}</a>
              </div>
              <div className="muted mono" style={{ marginTop: 4 }}>ev: {a.event_id.slice(0, 14)}</div>
            </div>
          </div>
        ))}
        {shown.length === 0 && <div className="empty">{t('noArtifacts')}</div>}
      </div>
    </div>
  )
}
