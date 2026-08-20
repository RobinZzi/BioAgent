import { useState } from 'react'
import type { Project } from '../types'

export default function ProjectColumn({
  projects, currentId, onSelect, onCreate,
}: {
  projects: Project[]
  currentId: string | null
  onSelect: (id: string) => void
  onCreate: (name: string, dataSource: string, computeLocation: string) => void
}) {
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [dataSource, setDataSource] = useState('local')
  const [computeLocation, setComputeLocation] = useState('local')

  const submit = () => {
    if (!name.trim()) return
    onCreate(name.trim(), dataSource, computeLocation)
    setName('')
    setShowForm(false)
  }

  return (
    <div className="col">
      <div className="col-header">
        <span>项目</span>
        <span className="spacer" />
        <button className="ghost" style={{ padding: '2px 8px', fontSize: 12 }}
                onClick={() => setShowForm(!showForm)}>
          {showForm ? '取消' : '新建'}
        </button>
      </div>

      <div className="col-body">
        {showForm && (
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
            <div key={p.id} className={`project-item ${p.id === currentId ? 'active' : ''}`}
                 onClick={() => onSelect(p.id)}>
              <div className="name">{p.name}</div>
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
    </div>
  )
}
