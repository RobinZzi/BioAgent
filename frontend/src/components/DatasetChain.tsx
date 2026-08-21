import { useState } from 'react'
import { api } from '../api'
import type { Dataset } from '../types'

const PHASE_COLOR: Record<string, string> = {
  raw: 'gray', qc: 'blue', normalized: 'blue', pca: 'blue', neighbors: 'blue',
  umap: 'blue', clustered: 'green', annotated: 'green', marker_genes: 'green',
  de: 'green', aligned: 'green', trimmed: 'blue',
}

const DTYPE_LABEL: Record<string, string> = {
  scrna: '单细胞 (h5ad)', bulk_rna: 'Bulk 矩阵 (csv)', fastq: '下机 (fastq)', other: '10x 矩阵目录 (mtx)',
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
  const [showFiles, setShowFiles] = useState(false)
  const [filePath, setFilePath] = useState('')
  const [fileData, setFileData] = useState<{ path: string; is_dir: boolean; dirs: string[]; files: { name: string; size: number }[] } | null>(null)

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

  const renameDataset = async (d: Dataset) => {
    const name = window.prompt('重命名数据集', d.name)
    if (!name || name.trim() === d.name) return
    try { await api.patchDataset(d.id, { name: name.trim() }); onRefresh() }
    catch (e) { alert((e as Error).message) }
  }

  const tagDataset = async (d: Dataset) => {
    const cur = ((d.metadata as { tags?: string[] })?.tags ?? []).join(',')
    const tags = window.prompt('标签（逗号分隔）', cur)
    if (tags === null) return
    try {
      await api.patchDataset(d.id, { tags: tags.split(',').map((t) => t.trim()).filter(Boolean) })
      onRefresh()
    } catch (e) { alert((e as Error).message) }
  }

  const removeDataset = async (d: Dataset) => {
    if (!window.confirm(`删除数据集「${d.name}」？仅删除记录，不删除原始文件。`)) return
    try { await api.deleteDataset(d.id); onRefresh() }
    catch (e) { alert((e as Error).message) }
  }

  const loadFiles = async (path: string) => {
    const r = await api.projectFiles(projectId, path)
    setFileData(r)
    setFilePath(path)
  }

  const dtypeChanged = (dtype: string) => {
    const fmt = dtype === 'scrna' ? 'h5ad' : dtype === 'bulk_rna' ? 'csv' : dtype === 'other' ? '10x_mtx' : 'fastq.gz'
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
        <button onClick={() => { setShowFiles(!showFiles); if (!showFiles) loadFiles('') }}>
          {showFiles ? '收起工作区' : '工作区文件'}
        </button>
        <button onClick={() => setShowForm(!showForm)}>
          {showForm ? '取消' : '注册数据集'}
        </button>
      </div>

      {showFiles && (
        <div className="dir-picker" style={{ margin: '10px 14px' }}>
          <div className="flex" style={{ marginBottom: 8 }}>
            <span className="muted mono" style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>{filePath || fileData?.path}</span>
            <button className="ghost sm" onClick={() => { const parts = filePath.split('/').filter(Boolean); parts.pop(); loadFiles(parts.join('/')) }}>上级</button>
          </div>
          <div className="dir-list">
            {fileData?.dirs.map((d) => (
              <div key={d} className="dir-item" onClick={() => loadFiles(`${filePath}/${d}`.replace(/^\/+/, ''))}>
                <span className="dir-icon" />{d}
              </div>
            ))}
            {fileData?.files.map((f) => (
              <div key={f.name} className="dir-item file">
                <span className="file-icon" />{f.name} <span className="muted mono">{(f.size / 1024).toFixed(1)}KB</span>
              </div>
            ))}
            {fileData && fileData.dirs.length === 0 && fileData.files.length === 0 && (
              <div className="muted" style={{ padding: 8 }}>（空工作区）</div>
            )}
          </div>
        </div>
      )}

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
              <option value="other">{DTYPE_LABEL.other}</option>
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
              <span className="ds-actions">
                <button className="ghost sm" title="重命名" onClick={() => renameDataset(d)}>改</button>
                <button className="ghost sm" title="打标签" onClick={() => tagDataset(d)}>标</button>
                <button className="ghost sm danger" title="删除" onClick={() => removeDataset(d)}>删</button>
              </span>
            </div>
          ))}
        </div>
      ))}
      {chains.length === 0 && <div className="empty">暂无数据集，点击「注册数据集」添加。</div>}
    </div>
  )
}
