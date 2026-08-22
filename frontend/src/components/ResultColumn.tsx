import { useState } from 'react'
import type { ProjectDetail } from '../types'
import { useI18n } from '../i18n'
import type { ResultTab } from '../App'
import AnalysisDAG from './AnalysisDAG'
import ArtifactGallery from './ArtifactGallery'
import CompareView from './CompareView'
import DatasetChain from './DatasetChain'
import EventDetail from './EventDetail'

export default function ResultColumn({
  detail, convId, tab, setTab, selectedEventId, setSelectedEventId, onRefresh,
}: {
  detail: ProjectDetail | null
  convId?: string
  tab: ResultTab
  setTab: (t: ResultTab) => void
  selectedEventId: string | null
  setSelectedEventId: (id: string | null) => void
  onRefresh: () => void
}) {
  const [compareMode, setCompareMode] = useState(false)
  const { t } = useI18n()
  const [compareIds, setCompareIds] = useState<string[]>([])

  if (!detail) {
    return (
      <div className="col">
        <div className="col-header"><span>{t('resultTabs')}</span></div>
        <div className="empty">{t('noProject')}</div>
      </div>
    )
  }

  const projectId = detail.project.id

  const toggleCompare = (id: string) => {
    setCompareIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id])
  }

  const closeCompare = () => {
    setCompareMode(false)
    setCompareIds([])
  }

  return (
    <div className="col">
      <div className="result-tabs">
        <button className={tab === 'dag' ? 'active' : ''} onClick={() => setTab('dag')}>{t('resultTabs')}</button>
        <button className={tab === 'artifacts' ? 'active' : ''} onClick={() => setTab('artifacts')}>{t('artifacts')}</button>
        <button className={tab === 'datasets' ? 'active' : ''} onClick={() => setTab('datasets')}>{t('datasetsTab')}</button>
      </div>

      <div className="col-body">
        {tab === 'dag' && (
          <AnalysisDAG
            dag={detail.dag}
            selectedEventId={selectedEventId}
            onSelect={setSelectedEventId}
            onRefresh={onRefresh}
            compareMode={compareMode}
            compareIds={compareIds}
            onToggleCompare={toggleCompare}
            onCompare={() => { if (compareIds.length >= 2) setSelectedEventId(null) }}
            onCloseCompare={compareMode ? closeCompare : () => setCompareMode(true)}
          />
        )}
        {tab === 'artifacts' && <ArtifactGallery projectId={projectId} />}
        {tab === 'datasets' && (
          <DatasetChain datasets={detail.datasets} projectId={projectId} onRefresh={onRefresh} />
        )}

        {tab === 'dag' && selectedEventId && !compareMode && (
          <EventDetail eventId={selectedEventId} onClose={() => setSelectedEventId(null)}
                       onChanged={onRefresh} />
        )}
        {tab === 'dag' && compareMode && compareIds.length >= 2 && (
          <CompareView eventIds={compareIds} onClose={closeCompare} />
        )}
      </div>
    </div>
  )
}
