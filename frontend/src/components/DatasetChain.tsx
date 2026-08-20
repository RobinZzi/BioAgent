import { useState } from 'react'
import { api } from '../api'
import type { Dataset } from '../types'

const PHASE_COLOR: Record<string, string> = {
  raw: 'gray', qc: 'blue', normalized: 'blue', pca: 'blue', neighbors: 'blue',
  umap: 'blue', clustered: 'green', annotated: 'green', marker_genes: 'green',
  de: 'green', aligned: 'green', trimmed: 'blue',
}

const DTYPE_LABEL: Record<string, string> = {
  scrna: '单细胞 (h5ad)', bulk_rna: 'Bulk 矩阵 (csv)', fastq: '下机 (fastq)',
}

export default function DatasetChain({
  datasets, projectId, onRefresh,
}: {
  datasets: Dataset[]
  projectId: string
  onRefresh: () => void
}) {
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', dtype: 'scrna', format: 'h5ad', location: '' })

  const register = async () => {
    if (!form.name.trim()) return
    try {
      await api.registerDataset(projectId, {
        name: form.name.trim(), dtype: form.dtype, format: form.format,
        location: form.location.trim(), phase: 'raw',
      })
      setForm({ name: '', dtype: 'scrna', format: 'h5ad', location: '' })
      setShowForm(false)
      onRefresh()
    } catch (e) { alert((e as Error).message) }
  }

  const dtypeChanged = (dtype: string) => {
    const fmt = dtype === 'scrna' ? 'h5ad' : dtype === 'bulk_rna' ? 'csv' : 'fastq.gz'
    setForm({ ...form, dtype, format: fmt })
  }

  // 按版本链组织：每条链从 root 开始
  const roots = datasets.filter((d) => !d.parent_dataset_id)
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
      <div className="flex" style={{ padding: '10px 14px 0' }}>
        <span className="muted">数据集版本链（引用语义，分析不破坏原始数据）</span>
        <span className="spacer" />
        <button onClick={() => setShowForm(!showForm)}>
          {showForm ? '取消' : '注册数据集'}
        </button>
      </div>

      {showForm && (
        <div className="card" style={{ margin: '10px 14px' }}>
          <div className="create-form">
            <input placeholder="文件名（如 sample_R1.fastq.gz）" value={form.name}
                   onChange={(e) => setForm({ ...form, name: e.target.value })}
                   style={{ minWidth: 220 }} />
            <select value={form.dtype} onChange={(e) => dtypeChanged(e.target.value)}>
              <option value="scrna">{DTYPE_LABEL.scrna}</option>
              <option value="bulk_rna">{DTYPE_LABEL.bulk_rna}</option>
              <option value="fastq">{DTYPE_LABEL.fastq}</option>
            </select>
            <input placeholder="本地路径（留空=生成 mock 占位）" value={form.location}
                   onChange={(e) => setForm({ ...form, location: e.target.value })}
                   style={{ minWidth: 220 }} />
            <button className="primary" onClick={register}>注册</button>
          </div>
          <div className="muted" style={{ marginTop: 6 }}>
            fastq 数据可继续「去接头」→「比对」→「定量」，得到 count matrix 后做差异表达。
          </div>
        </div>
      )}

      {chains.map((chain, ci) => (
        <div key={ci} className="dataset-chain" style={{ marginBottom: 16 }}>
          {chain.map((d, i) => (
            <div key={d.id} className="ds-row">
              {i > 0 && <span className="arrow">↓</span>}
              <span className={`badge ${PHASE_COLOR[d.phase] ?? 'gray'}`}>{d.phase}</span>
              <span className="badge gray">{DTYPE_LABEL[d.dtype] ?? d.dtype}</span>
              <span style={{ fontWeight: 500, fontSize: 12.5 }}>{d.name}</span>
              <span className="muted mono" style={{ marginLeft: 'auto' }}>{d.id.slice(0, 12)}</span>
            </div>
          ))}
        </div>
      ))}
      {chains.length === 0 && <div className="empty">暂无数据集，点击「注册数据集」添加。</div>}
    </div>
  )
}
