import type { ProjectDetail } from '../types'
import type { ResultTab } from '../App'
import AnalysisDAG from './AnalysisDAG'
import ArtifactGallery from './ArtifactGallery'
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
  if (!detail) {
    return (
      <div className="col">
        <div className="col-header"><span>历史结果</span></div>
        <div className="empty">选择一个项目查看分析历史。</div>
      </div>
    )
  }

  const projectId = detail.project.id

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
          />
        )}
        {tab === 'artifacts' && <ArtifactGallery projectId={projectId} />}
        {tab === 'datasets' && <DatasetChain datasets={detail.datasets} />}

        {tab === 'dag' && selectedEventId && (
          <EventDetail eventId={selectedEventId} onClose={() => setSelectedEventId(null)} />
        )}
      </div>
    </div>
  )
}
