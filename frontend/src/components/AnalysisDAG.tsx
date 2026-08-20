import { useState } from 'react'
import { api } from '../api'
import type { Dag, DagNode } from '../types'

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

export default function AnalysisDAG({
  dag, selectedEventId, onSelect, onRefresh,
}: {
  dag: Dag
  selectedEventId: string | null
  onSelect: (id: string) => void
  onRefresh: () => void
}) {
  const [rerunning, setRerunning] = useState<string | null>(null)

  if (!dag || dag.nodes.length === 0) {
    return <div className="empty">还没有分析事件。在对话中发出第一个分析请求，例如「聚类，分辨率 0.5」。</div>
  }

  const maxDepth = Math.max(0, ...dag.nodes.map((n) => dag.depth[n.id] ?? 0))
  const layers: DagNode[][] = Array.from({ length: maxDepth + 1 }, () => [])
  for (const n of dag.nodes) layers[dag.depth[n.id] ?? 0].push(n)

  const rerun = async (node: DagNode) => {
    if (!confirm(`重跑事件 ${node.capability_id}（参数默认为原参数）？新事件将以 re_run 边挂到 DAG。`)) return
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

  return (
    <div>
      <div className="dag-layers">
        {layers.map((layer, depth) => (
          <div key={depth} className="dag-layer">
            <div className="dag-layer-label">步骤 {depth}</div>
            {layer.map((n) => (
              <div key={n.id}
                   className={`dag-node ${statusClass(n.status)} ${n.id === selectedEventId ? 'selected' : ''}`}
                   onClick={() => onSelect(n.id)} title={n.id}>
                <div className="cap">{CAP_LABEL[n.capability_id] ?? n.capability_id}</div>
                <div className="meta">
                  <span className="mono">{n.id.slice(0, 14)}</span> · impl: {n.implementation}
                </div>
                {paramSummary(n) && <div className="meta mono">{paramSummary(n)}</div>}
                <div className="actions">
                  <span className={`badge ${n.status === 'succeeded' ? 'green' : n.status === 'failed' ? 'red' : 'amber'}`}>
                    {n.status}
                  </span>
                  {n.status === 'succeeded' && (
                    <button onClick={(e) => { e.stopPropagation(); rerun(n) }} disabled={rerunning === n.id}>
                      重跑
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>

      <div className="muted" style={{ marginTop: 8, padding: '0 14px' }}>
        依赖边由数据集版本链推导，重跑以 <span className="mono">re_run</span> 边标记（fork）。点击节点查看详情。
      </div>
    </div>
  )
}
