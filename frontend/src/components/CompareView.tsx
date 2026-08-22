import { useEffect, useState } from 'react'
import { api } from '../api'
import type { AnalysisEvent } from '../types'
import { useI18n } from '../i18n'
import { capLabel } from '../capNames'


/** 分析历史对比视图：并排对比多个事件的参数 / 指标 / 产物，差异参数高亮。 */
export default function CompareView({ eventIds, onClose }: {
  eventIds: string[]
  onClose: () => void
}) {
  const { t, lang } = useI18n()
  const [events, setEvents] = useState<AnalysisEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all(eventIds.map((id) => api.event(id).catch(() => null)))
      .then((list) => setEvents(list.filter(Boolean) as AnalysisEvent[]))
      .finally(() => setLoading(false))
  }, [eventIds.join(',')]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <div className="empty">{t('loadingCompare')}</div>
  if (events.length < 2) return <div className="empty">{t('minCompare')}</div>

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
        <b>{t('paramCompare')}</b>
        <span className="muted">({t('highlightNote')})</span>
        <span className="spacer" />
        <button onClick={onClose}>{t('closeCompare')}</button>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="kv-table">
          <thead>
            <tr>
              <th style={{ minWidth: 120 }}>{t('events')}</th>
              {events.map((e) => (
                <th key={e.id} style={{ minWidth: 180 }}>
                  {capLabel(e.capability_id, lang)}
                  <div className="muted mono" style={{ fontWeight: 400 }}>
                    {e.id.slice(0, 14)} · {e.status}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{t('executorMode')}</td>
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
        <b>{t('artifactCompare')}</b>
        <div className="artifact-grid" style={{ padding: '10px 0 0' }}>
          {events.map((e, i) => (
            <div key={e.id}>
              <div className="muted" style={{ marginBottom: 6 }}>
                {capLabel(e.capability_id, lang)}（{e.id.slice(0, 10)}）
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {figures[i].map((a) => (
                  <img key={a.id} src={api.artifactUrl(a.id)} alt={a.name}
                       style={{ width: '100%', border: '1px solid var(--border)', borderRadius: 4 }} />
                ))}
                {figures[i].length === 0 && <span className="muted">{t('noFigure')}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
