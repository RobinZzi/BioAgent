import { useEffect, useState } from 'react'
import { api } from '../api'
import type { AnalysisEvent, Diagnosis } from '../types'
import { useI18n, Lang } from '../i18n'
import { capLabel } from '../capNames'


export default function EventDetail({ eventId, onClose, onChanged }: {
  eventId: string
  onClose: () => void
  onChanged?: () => void
}) {
  const { t, lang } = useI18n()
  const [ev, setEv] = useState<AnalysisEvent | null>(null)
  const [logs, setLogs] = useState('')
  const [showLogs, setShowLogs] = useState(false)
  const [liveLogs, setLiveLogs] = useState('')
  const [liveOn, setLiveOn] = useState(false)
  const [diagnosis, setDiagnosis] = useState<Diagnosis | null>(null)
  const [showDiagnosis, setShowDiagnosis] = useState(false)
  const [diagnosing, setDiagnosing] = useState(false)
  const [rerunning, setRerunning] = useState(false)

  useEffect(() => {
    setEv(null)
    setShowLogs(false)
    setLogs('')
    setLiveLogs('')
    setDiagnosis(null)
    api.event(eventId).then(setEv).catch(console.error)
  }, [eventId])

  // SSE 实时日志流
  useEffect(() => {
    if (!liveOn) return
    const token = localStorage.getItem('bioagent_token') ?? ''
    const es = new EventSource(`/api/events/${eventId}/stream?token=${encodeURIComponent(token)}`)
    es.onmessage = (e) => setLiveLogs((prev) => prev + e.data + '\n')
    es.addEventListener('done', () => { es.close(); setLiveOn(false) })
    es.onerror = () => { es.close(); setLiveOn(false) }
    return () => es.close()
  }, [liveOn, eventId])

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
      alert(t('rerunDone'))
      onChanged?.()
    } catch (e) { alert((e as Error).message) } finally { setRerunning(false) }
  }

  if (!ev) return <div className="empty">{t('loadingEvent')}</div>

  return (
    <div className="event-detail">
      <div className="flex" style={{ marginBottom: 8 }}>
        <span style={{ fontWeight: 600 }}>{capLabel(ev.capability_id, lang)}</span>
        <span className={`badge ${ev.status === 'succeeded' ? 'green' : ev.status === 'failed' ? 'red' : 'amber'}`}>
          {ev.status}
        </span>
        <span className="muted mono">{ev.id}</span>
        <span className="spacer" />
        <button onClick={() => setLiveOn(!liveOn)}>{liveOn ? t('stopLive') : t('liveLogs')}</button>
        <button onClick={loadLogs}>{showLogs ? t('collapseLogs') : t('viewLogs')}</button>
        <button onClick={onClose}>{t('close')}</button>
      </div>

      {liveOn && (
        <div style={{ marginTop: 10 }}>
          <div className="muted" style={{ marginBottom: 4 }}>{t('liveLogsAuto')}</div>
          <pre className="logs" ref={(el) => { if (el) el.scrollTop = el.scrollHeight }}>
            {liveLogs || t('waitingLogs')}
          </pre>
        </div>
      )}

      {ev.error && (
        <div className="card" style={{ background: 'var(--red-soft)', borderColor: 'var(--red)', marginBottom: 10 }}>
          <div className="flex" style={{ alignItems: 'flex-start' }}>
            <div style={{ flex: 1 }}>
              <b style={{ color: 'var(--red)' }}>{t('execFail')}: {ev.error.message}</b>
              {ev.error.stage && <div className="muted">stage: {ev.error.stage} · type: {ev.error.type}</div>}
            </div>
            <button onClick={diagnose} disabled={diagnosing}>
              {diagnosing ? t('diagnosing') : t('diagnoseBtn')}
            </button>
          </div>
          {showDiagnosis && diagnosis && (
            <div style={{ marginTop: 10, background: 'var(--panel)', borderRadius: 8, padding: 10 }}>
              <div style={{ marginBottom: 6 }}>{diagnosis.message}</div>
              {Object.keys(diagnosis.suggested_params).length > 0 && (
                <div className="mono muted" style={{ marginBottom: 8 }}>
                  {t('suggestedParams')}: {JSON.stringify(diagnosis.suggested_params)}
                </div>
              )}
              {Object.keys(diagnosis.suggested_params).length > 0 && (
                <button className="primary" onClick={rerunWithSuggested} disabled={rerunning}>
                  {rerunning ? t('rerunning') : t('rerunSuggested')}
                </button>
              )}
            </div>
          )}
        </div>
      )}

      <div className="detail-grid">
        <div>
          <div className="kv"><span className="k">{t('implementation')}</span><span className="mono">{ev.implementation}{ev.runtime_id ? ` @ ${ev.runtime_id}` : ''}</span></div>
          <div className="kv"><span className="k">{t('inputDataset')}</span><span className="mono">{(ev.inputs.dataset as string) ?? '—'}</span></div>
          <div className="kv"><span className="k">{t('params')}</span><span className="mono">{JSON.stringify(ev.parameters)}</span></div>
          <div className="kv"><span className="k">{t('executorMode')}</span><span className="mono">{String(ev.metrics.executor_mode ?? '—')}</span></div>
          {Object.entries(ev.metrics).filter(([k]) => k !== 'executor_mode').map(([k, v]) => (
            <div className="kv" key={k}><span className="k">{k}</span><span className="mono">{String(v)}</span></div>
          ))}
        </div>
        <div>
          <div className="muted" style={{ marginBottom: 4 }}>{t('artifacts')}（{ev.artifacts.length}）</div>
          {ev.artifacts.map((a) => (
            <div className="kv" key={a.id}>
              <span className="badge gray">{a.kind}</span>
              <a href={api.artifactUrl(a.id)} target="_blank" rel="noreferrer">{a.name}</a>
            </div>
          ))}
          {ev.artifacts.length === 0 && <div className="muted">{t("noArtifacts")}</div>}
        </div>
      </div>

      {showLogs && (
        <div style={{ marginTop: 10 }}>
          <pre className="logs">{logs || t('noLogs')}</pre>
        </div>
      )}
    </div>
  )
}
