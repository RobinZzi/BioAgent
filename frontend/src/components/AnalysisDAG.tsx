import { useState } from 'react'
import { api } from '../api'
import type { Dag, DagNode } from '../types'
import { useI18n } from '../i18n'
import { capLabel } from '../capNames'


export default function AnalysisDAG({
  dag, selectedEventId, onSelect, onRefresh,
  compareMode, compareIds, onToggleCompare, onCompare, onCloseCompare,
}: {
  dag: Dag
  selectedEventId: string | null
  onSelect: (id: string) => void
  onRefresh: () => void
  compareMode: boolean
  compareIds: string[]
  onToggleCompare: (id: string) => void
  onCompare: () => void
  onCloseCompare: () => void
}) {
  const { t, lang } = useI18n()
  const [rerunning, setRerunning] = useState<string | null>(null)

  if (!dag || dag.nodes.length === 0) {
    return <div className="empty">{t('noEvent')}</div>
  }

  const maxDepth = Math.max(0, ...dag.nodes.map((n) => dag.depth[n.id] ?? 0))
  const layers: DagNode[][] = Array.from({ length: maxDepth + 1 }, () => [])
  for (const n of dag.nodes) layers[dag.depth[n.id] ?? 0].push(n)

  // 依赖连线：构建 子节点 → 父节点 映射（depends_on / re_run）
  const nodeById = new Map(dag.nodes.map((n) => [n.id, n]))
  const parentMap = new Map<string, { id: string; relation: string }[]>()
  for (const e of dag.edges) {
    const list = parentMap.get(e.target) ?? []
    list.push({ id: e.source, relation: e.relation })
    parentMap.set(e.target, list)
  }
  const depsLabel = (n: DagNode) => {
    const parents = parentMap.get(n.id) ?? []
    if (parents.length === 0) return ''
    const names = parents.map((p) => {
      const pn = nodeById.get(p.id)
      const label = pn ? (capLabel(pn.capability_id, lang)) : p.id.slice(0, 10)
      return p.relation === 're_run' ? `${label}(${t('rerunShort')})` : label
    })
    return names.join(' + ')
  }

  const rerun = async (node: DagNode) => {
    if (!confirm(`${t('rerunConfirm')} ${node.capability_id}`)) return
    setRerunning(node.id)
    try {
      await api.rerunEvent(node.id, {})
      onRefresh()
    } catch (e) {
      alert((e as Error).message)
    } finally {
      setRerunning(null)
    }
  }

  const statusClass = (s: string) =>
    s === 'succeeded' ? 'done' : s === 'failed' ? 'failed' : s === 'running' ? 'running' : 'queued'

  const paramSummary = (n: DagNode) => {
    const p = n.parameters as Record<string, unknown>
    const keys = Object.keys(p)
    return keys.length ? keys.map((k) => `${k}=${p[k]}`).join(' ') : ''
  }

  const nodeClick = (n: DagNode) => {
    if (compareMode) onToggleCompare(n.id)
    else onSelect(n.id)
  }

  return (
    <div>
      <div className="flex" style={{ padding: '10px 14px 0' }}>
        <span className="muted">{t('dagLegend')}</span>
        <span className="spacer" />
        {compareMode ? (
          <>
            <span className="muted">{t('selectedCount')} {compareIds.length}</span>
            <button className="primary" onClick={onCompare} disabled={compareIds.length < 2}>
              {t('compare')}
            </button>
            <button onClick={onCloseCompare}>{t('cancel')}</button>
          </>
        ) : (
          <button onClick={onCloseCompare}>{t('compareEvents')}</button>
        )}
      </div>

      <div className="dag-layers">
        {layers.map((layer, depth) => (
          <div key={depth} style={{ display: 'contents' }}>
            {depth > 0 && (
              <div className="dag-layer-arrow" aria-hidden="true">
                <span className="line" />
                <svg viewBox="0 0 10 12" width="8" height="12" fill="none"
                     stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2 1l6 5-6 5" />
                </svg>
              </div>
            )}
            <div className="dag-layer">
              <div className="dag-layer-label">{t('step')} {depth}</div>
              {layer.map((n) => (
                <div key={n.id}
                     className={`dag-node ${statusClass(n.status)} ${(n.id === selectedEventId || compareIds.includes(n.id)) ? 'selected' : ''}`}
                     onClick={() => nodeClick(n)} title={n.id}>
                  <div className="cap">
                    {compareMode && (
                      <input type="checkbox" style={{ marginRight: 6 }}
                             checked={compareIds.includes(n.id)}
                             onChange={() => onToggleCompare(n.id)}
                             onClick={(e) => e.stopPropagation()} />
                    )}
                    <span className={`status-dot ${statusClass(n.status)}`} aria-hidden="true" />
                    {capLabel(n.capability_id, lang)}
                  </div>
                  <div className="meta">
                    <span className="mono">{n.id.slice(0, 14)}</span> · impl: {n.implementation}
                  </div>
                  {paramSummary(n) && <div className="meta mono">{paramSummary(n)}</div>}
                  {depsLabel(n) && (
                    <div className="meta" style={{ color: 'var(--text-faint)' }}>
                      {t('deps')}: {depsLabel(n)}
                    </div>
                  )}
                  <div className="actions">
                  <span className={`badge ${n.status === 'succeeded' ? 'green' : n.status === 'failed' ? 'red' : 'amber'}`}>
                    {n.status}
                  </span>
                  {n.status === 'succeeded' && !compareMode && (
                    <button onClick={(e) => { e.stopPropagation(); rerun(n) }} disabled={rerunning === n.id}>
                      {t('rerun')}
                    </button>
                  )}
                </div>
              </div>
            ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
