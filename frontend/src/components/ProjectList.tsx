import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { Project } from '../types'

export default function ProjectList({ onOpen }: { onOpen: (id: string) => void }) {
  const [projects, setProjects] = useState<Project[]>([])
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [dataSource, setDataSource] = useState('local')
  const [computeLocation, setComputeLocation] = useState('local')

  const refresh = useCallback(() => {
    api.listProjects().then(setProjects).catch(console.error)
  }, [])

  useEffect(refresh, [refresh])

  const create = async () => {
    if (!name.trim()) return
    try {
      const p = await api.createProject({
        name: name.trim(), description, data_source: dataSource,
        compute_location: computeLocation,
      })
      await api.createConversation(p.id)
      setShowForm(false)
      setName(''); setDescription('')
      refresh()
    } catch (e) { alert((e as Error).message) }
  }

  return (
    <div className="page">
      <h1>🧬 BioAgent · 生信分析工作台</h1>
      <p className="muted">
        选择一个项目进入分析工作区。项目对应一个数据来源 / 一个科研课题，项目内是连贯的分析对话。
      </p>

      <div className="flex">
        <button className="primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? '取消' : '+ 新建项目'}
        </button>
        <button onClick={refresh}>刷新</button>
      </div>

      {showForm && (
        <div className="card create-form">
          <input placeholder="项目名称（如 HCC Single-cell Analysis）" value={name}
                 onChange={(e) => setName(e.target.value)} style={{ minWidth: 280 }} />
          <input placeholder="描述（可选）" value={description}
                 onChange={(e) => setDescription(e.target.value)} style={{ minWidth: 220 }} />
          <select value={dataSource} onChange={(e) => setDataSource(e.target.value)} title="数据在哪里">
            <option value="local">数据：本地</option>
            <option value="remote">数据：远程</option>
          </select>
          <select value={computeLocation} onChange={(e) => setComputeLocation(e.target.value)} title="计算在哪里">
            <option value="local">计算：本地</option>
            <option value="remote">计算：远程 / HPC</option>
          </select>
          <button className="primary" onClick={create}>创建</button>
        </div>
      )}

      <div className="project-grid">
        {projects.map((p) => (
          <div key={p.id} className="card project-card" onClick={() => onOpen(p.id)}>
            <h3>📁 {p.name}</h3>
            {p.description && <p className="muted" style={{ margin: '4px 0 0' }}>{p.description}</p>}
            <div className="stats">
              <span className="badge gray">数据 {p.data_source === 'local' ? '本地' : '远程'}</span>
              <span className="badge gray">计算 {p.compute_location === 'local' ? '本地' : '远程'}</span>
              <span className="badge blue">{p.n_conversations} 对话</span>
              <span className="badge blue">{p.n_datasets} 数据集</span>
              <span className="badge blue">{p.n_events} 事件</span>
            </div>
          </div>
        ))}
        {projects.length === 0 && <div className="empty">还没有项目，点击「+ 新建项目」开始。</div>}
      </div>
    </div>
  )
}
