import type { Dataset } from '../types'

const PHASE_COLOR: Record<string, string> = {
  raw: 'gray', qc: 'blue', normalized: 'blue', pca: 'blue', neighbors: 'blue',
  umap: 'blue', clustered: 'green', annotated: 'green', marker_genes: 'green',
  de: 'green', aligned: 'green',
}

export default function DatasetChain({ datasets }: { datasets: Dataset[] }) {
  const byId = new Map(datasets.map((d) => [d.id, d]))
  const roots = datasets.filter((d) => !d.parent_dataset_id)

  // 按版本链组织：每条链从 root 开始
  const chains: Dataset[][] = []
  for (const root of roots) {
    const chain: Dataset[] = [root]
    let cur = root
    let guard = 0
    while (guard++ < 100) {
      const next = datasets.find((d) => d.parent_dataset_id === cur.id)
      if (!next) break
      chain.push(next)
      cur = next
    }
    chains.push(chain)
  }

  return (
    <div>
      <div className="muted" style={{ marginBottom: 10 }}>
        数据集版本链（引用语义，分析不破坏原始数据）：
      </div>
      {chains.map((chain, ci) => (
        <div key={ci} className="dataset-chain" style={{ marginBottom: 16 }}>
          {chain.map((d, i) => (
            <div key={d.id} className="ds-row">
              {i > 0 && <span className="arrow">↓</span>}
              <span className={`badge ${PHASE_COLOR[d.phase] ?? 'gray'}`}>{d.phase}</span>
              <span style={{ fontWeight: 600, fontSize: 13 }}>{d.name}</span>
              <span className="muted mono" style={{ marginLeft: 'auto' }}>{d.id.slice(0, 12)}</span>
            </div>
          ))}
        </div>
      ))}
      {chains.length === 0 && <div className="empty">暂无数据集。可在项目详情中注册数据集。</div>}
    </div>
  )
}
