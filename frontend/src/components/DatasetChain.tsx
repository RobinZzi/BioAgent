import { useState } from 'react'
import { api } from '../api'
import type { Dataset } from '../types'
import { useI18n } from '../i18n'

const PHASE_COLOR: Record<string, string> = {
  raw: 'gray', qc: 'blue', normalized: 'blue', pca: 'blue', neighbors: 'blue',
  umap: 'blue', clustered: 'green', annotated: 'green', marker_genes: 'green',
  de: 'green', aligned: 'green', trimmed: 'blue',
}



export default function DatasetChain({
  datasets, projectId, onRefresh,
}: {
  datasets: Dataset[]
  projectId: string
  onRefresh: () => void
}) {
  const { t } = useI18n()
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
    const name = window.prompt(t('rename'), d.name)
    if (!name || name.trim() === d.name) return
    try { await api.patchDataset(d.id, { name: name.trim() }); onRefresh() }
    catch (e) { alert((e as Error).message) }
  }

  const tagDataset = async (d: Dataset) => {
    const cur = ((d.metadata as { tags?: string[] })?.tags ?? []).join(',')
    const tags = window.prompt(t('tagsPrompt'), cur)
    if (tags === null) return
    try {
      await api.patchDataset(d.id, { tags: tags.split(',').map((t) => t.trim()).filter(Boolean) })
      onRefresh()
    } catch (e) { alert((e as Error).message) }
  }

  const removeDataset = async (d: Dataset) => {
    if (!window.confirm(`${t('deleteDatasetConfirm')} ${d.name}`)) return
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
        <span className="muted">{t('datasetChainNote')}</span>
        <span className="spacer" />
        <button onClick={() => { setShowFiles(!showFiles); if (!showFiles) loadFiles('') }}>
          {showFiles ? t('collapseWorkspace') : t('workspaceFiles')}
        </button>
        <button onClick={() => setShowForm(!showForm)}>
          {showForm ? t('cancel') : t('registerDataset')}
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
              <div className="muted" style={{ padding: 8 }}>{t('emptyWorkspace')}</div>
            )}
          </div>
        </div>
      )}

      {showForm && (
        <div className="card" style={{ margin: '10px 14px' }}>
          <div className="create-form">
            <input placeholder={t("fileName")} value={form.name}
                   onChange={(e) => setForm({ ...form, name: e.target.value })}
                   style={{ minWidth: 220 }} />
            <select value={form.dtype} onChange={(e) => dtypeChanged(e.target.value)}>
              <option value="scrna">{t('scrna')}</option>
              <option value="bulk_rna">{t('bulk_rna')}</option>
              <option value="fastq">{t('fastq')}</option>
              <option value="other">{t('other')}</option>
            </select>
            <input placeholder={t("filePath")} value={form.location}
                   onChange={(e) => setForm({ ...form, location: e.target.value })}
                   style={{ minWidth: 220 }} />
            <button className="primary" onClick={register}>{t('registerBtn')}</button>
          </div>
          <div className="muted" style={{ marginTop: 6 }}>
            {t('fastqHint')}
          </div>
        </div>
      )}

      {chains.map((chain, ci) => (
        <div key={ci} className="dataset-chain" style={{ marginBottom: 16 }}>
          {chain.map((d, i) => (
            <div key={d.id} className="ds-row">
              {i > 0 && <span className="arrow">↓</span>}
              <span className={`badge ${PHASE_COLOR[d.phase] ?? 'gray'}`}>{d.phase}</span>
              <span className="badge gray">{t(d.dtype)}</span>
              <span style={{ fontWeight: 500, fontSize: 12.5 }}>{d.name}</span>
              <span className="muted mono" style={{ marginLeft: 'auto' }}>{d.id.slice(0, 12)}</span>
              <span className="ds-actions">
                <button className="ghost sm" title={t('rename')} onClick={() => renameDataset(d)}>{t('rename')}</button>
                <button className="ghost sm" title={t('tag')} onClick={() => tagDataset(d)}>{t('tag')}</button>
                <button className="ghost sm danger" title={t('delete')} onClick={() => removeDataset(d)}>{t('delete')}</button>
              </span>
            </div>
          ))}
        </div>
      ))}
      {chains.length === 0 && <div className="empty">{t('noDatasets')}</div>}
    </div>
  )
}
