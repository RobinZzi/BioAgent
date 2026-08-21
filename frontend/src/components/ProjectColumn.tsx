import { useState } from 'react'
import type { Project } from '../types'

export default function ProjectColumn({
  projects, currentId, onSelect, onCreate, onDelete,
}: {
  projects: Project[]
  currentId: string | null
  onSelect: (id: string) => void
  onCreate: (name: string, dataSource: string, computeLocation: string) => void
  onDelete: (ids: string[], deleteFiles: boolean) => void
}) {
  const [showForm, setShowForm] = useState(false)
  const [manage, setManage] = useState(false)
  const [selected, setSelected] = useState<string[]>([])
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleteFiles, setDeleteFiles] = useState(true)
  const [name, setName] = useState('')
  const [dataSource, setDataSource] = useState('local')
  const [computeLocation, setComputeLocation] = useState('local')

  const submit = () => {
    if (!name.trim()) return
    onCreate(name.trim(), dataSource, computeLocation)
    setName('')
    setShowForm(false)
  }

  const toggleSelect = (id: string) => {
    setSelected((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id])
  }

  const exitManage = () => {
    setManage(false)
    setSelected([])
    setConfirmOpen(false)
  }

  const doDelete = () => {
    onDelete(selected, deleteFiles)
    exitManage()
  }

  return (
    <div className="col">
      <div className="col-header">
        <span>项目</span>
        <span className="spacer" />
        {manage ? (
          <>
            <span className="muted">已选 {selected.length}</span>
            <button className="danger" style={{ padding: '2px 8px', fontSize: 12 }}
                    disabled={selected.length === 0}
                    onClick={() => setConfirmOpen(true)}>
              删除
            </button>
            <button className="ghost" style={{ padding: '2px 8px', fontSize: 12 }} onClick={exitManage}>
              取消
            </button>
          </>
        ) : (
          <>
            <button className="ghost" style={{ padding: '2px 8px', fontSize: 12 }}
                    onClick={() => setShowForm(!showForm)}>
              {showForm ? '取消' : '新建'}
            </button>
            <button className="ghost" style={{ padding: '2px 8px', fontSize: 12 }}
                    onClick={() => setManage(true)}>
              管理
            </button>
          </>
        )}
      </div>

      <div className="col-body">
        {showForm && !manage && (
          <div className="new-project">
            <input placeholder="项目名称" value={name}
                   onChange={(e) => setName(e.target.value)} autoFocus />
            <div className="row">
              <select value={dataSource} onChange={(e) => setDataSource(e.target.value)}>
                <option value="local">数据 · 本地</option>
                <option value="remote">数据 · 远程</option>
              </select>
              <select value={computeLocation} onChange={(e) => setComputeLocation(e.target.value)}>
                <option value="local">计算 · 本地</option>
                <option value="remote">计算 · 远程/HPC</option>
              </select>
            </div>
            <button className="primary" style={{ width: '100%' }} onClick={submit}>创建项目</button>
          </div>
        )}

        <div className="project-list">
          {projects.map((p) => (
            <div key={p.id}
                 className={`project-item ${p.id === currentId ? 'active' : ''} ${selected.includes(p.id) ? 'selected' : ''}`}
                 onClick={() => manage ? toggleSelect(p.id) : onSelect(p.id)}>
              <div className="name">
                {manage && (
                  <input type="checkbox" style={{ marginRight: 8 }}
                         checked={selected.includes(p.id)}
                         onChange={() => toggleSelect(p.id)}
                         onClick={(e) => e.stopPropagation()} />
                )}
                {p.name}
              </div>
              <div className="meta">
                {p.n_datasets} 数据集 · {p.n_events} 事件
              </div>
            </div>
          ))}
          {projects.length === 0 && (
            <div className="empty">暂无项目，点击「新建」创建。</div>
          )}
        </div>
      </div>

      {confirmOpen && (
        <div className="settings-overlay" onClick={() => setConfirmOpen(false)}>
          <div className="confirm-panel" onClick={(e) => e.stopPropagation()}>
            <b>删除 {selected.length} 个项目？</b>
            <div className="muted" style={{ margin: '6px 0 10px' }}>
              将删除：{selected.map((id) => projects.find((p) => p.id === id)?.name).join('、')}
            </div>
            <label className="flex" style={{ marginBottom: 14 }}>
              <input type="checkbox" checked={deleteFiles}
                     onChange={(e) => setDeleteFiles(e.target.checked)} />
              <span>同时删除 log 和已生成的图片/产物文件（不可恢复）</span>
            </label>
            <div className="flex" style={{ justifyContent: 'flex-end' }}>
              <button onClick={() => setConfirmOpen(false)}>取消</button>
              <button className="primary danger" onClick={doDelete}>确认删除</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
