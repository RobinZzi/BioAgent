import { useState } from 'react'
import type { ProjectDetail } from '../types'
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
  const [compareIds, setCompareIds] = useState<string[]>([])

  if (!detail) {
    return (
      <div className="col">
        <div className="col-header"><span>历史结果</span></div>
        <div className="empty">选择一个项目查看分析历史。</div>
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
        <button className={tab === 'dag' ? 'active' : ''} onClick={() => setTab('dag')}>历史 DAG</button>
        <button className={tab === 'artifacts' ? 'active' : ''} onClick={() => setTab('artifacts')}>产物</button>
        <button className={tab === 'datasets' ? 'active' : ''} onClick={() => setTab('datasets')}>数据集</button>
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
