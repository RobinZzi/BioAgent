import { useState } from 'react'
import { api } from '../api'
import type { Project } from '../types'
import NewProjectModal from './NewProjectModal'

function LocalIcon() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true">
      <rect x="2" y="3" width="12" height="7" rx="1.2" />
      <path d="M6 12h4M8 10v2" />
    </svg>
  )
}
function ServerIcon() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true">
      <rect x="2" y="2" width="12" height="4.5" rx="1.2" />
      <rect x="2" y="9.5" width="12" height="4.5" rx="1.2" />
      <path d="M5 4.2h.01M5 11.7h.01M8 4.2h.01M8 11.7h.01" />
    </svg>
  )
}

const DTYPE_LABEL: Record<string, string> = { local: '本地', remote: '服务器' }

export default function ProjectColumn({
  projects, currentId, onSelect, onCreate, onDelete, onRefresh,
}: {
  projects: Project[]
  currentId: string | null
  onSelect: (id: string) => void
  onCreate: (name: string, category: 'local' | 'remote', workdir: string, serverId: string) => void
  onDelete: (ids: string[], deleteFiles: boolean) => void
  onRefresh: () => void
}) {
  const [showModal, setShowModal] = useState(false)
  const [manage, setManage] = useState(false)
  const [selected, setSelected] = useState<string[]>([])
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleteFiles, setDeleteFiles] = useState(true)

  const local = projects.filter((p) => p.data_source === 'local')
  const remote = projects.filter((p) => p.data_source === 'remote')

  // 服务器端项目按服务器归属分组（服务器名 + IP）
  const remoteGroups = new Map<string, Project[]>()
  for (const p of remote) {
    const key = p.server_name ?? p.server_host ?? '未指定服务器'
    if (!remoteGroups.has(key)) remoteGroups.set(key, [])
    remoteGroups.get(key)!.push(p)
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

  const rename = async (p: Project) => {
    const name = window.prompt('重命名项目', p.name)
    if (!name || name.trim() === p.name) return
    try {
      await api.patchProject(p.id, { name: name.trim() })
      onRefresh()
    } catch (e) { alert((e as Error).message) }
  }

  const reposition = async (p: Project) => {
    const wd = window.prompt('重定位工作区（本地绝对路径 / 服务器目录名）', p.workdir ?? '')
    if (wd === null) return
    try {
      await api.patchProject(p.id, { workdir: wd.trim() })
      onRefresh()
    } catch (e) { alert((e as Error).message) }
  }

  const renderItem = (p: Project) => (
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
        <span className="badge gray">{DTYPE_LABEL[p.data_source] ?? p.data_source}</span>
        {p.n_datasets} 数据集 · {p.n_events} 事件
        {p.data_source === 'remote' && p.server_host && (
          <span className="mono muted" style={{ display: 'block', marginTop: 2 }}>
            {p.server_name} · {p.server_host}
          </span>
        )}
        {p.workdir && <span className="mono muted" style={{ display: 'block', marginTop: 2 }}>{p.workdir}</span>}
      </div>
      {manage && selected.includes(p.id) && selected.length === 1 && (
        <div className="actions" style={{ marginTop: 6, display: 'flex', gap: 6 }}>
          <button className="ghost" style={{ fontSize: 11 }} onClick={(e) => { e.stopPropagation(); rename(p) }}>重命名</button>
          <button className="ghost" style={{ fontSize: 11 }} onClick={(e) => { e.stopPropagation(); reposition(p) }}>重定位</button>
        </div>
      )}
    </div>
  )

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
                    onClick={() => setConfirmOpen(true)}>删除</button>
            <button className="ghost" style={{ padding: '2px 8px', fontSize: 12 }} onClick={exitManage}>取消</button>
          </>
        ) : (
          <>
            <button className="ghost" style={{ padding: '2px 8px', fontSize: 12 }}
                    onClick={() => setShowModal(true)}>新建</button>
            <button className="ghost" style={{ padding: '2px 8px', fontSize: 12 }}
                    onClick={() => setManage(true)}>管理</button>
          </>
        )}
      </div>

      <div className="col-body">
        {local.length > 0 && (
          <div className="group-header"><span className="group-icon"><LocalIcon /></span>本地项目</div>
        )}
        <div className="project-list">{local.map(renderItem)}</div>
        {remote.length > 0 && (
          <div className="group-header"><span className="group-icon"><ServerIcon /></span>服务器端项目</div>
        )}
        {[...remoteGroups.entries()].map(([serverKey, items]) => (
          <div key={serverKey}>
            <div className="group-header server-group" style={{ paddingLeft: 28 }}>
              {serverKey}
            </div>
            <div className="project-list">{items.map(renderItem)}</div>
          </div>
        ))}
        {projects.length === 0 && (
          <div className="empty">暂无项目，点击「新建」创建。</div>
        )}
      </div>

      {showModal && (
        <NewProjectModal
          onClose={() => setShowModal(false)}
          onCreate={(name, cat, wd, sid) => { onCreate(name, cat, wd, sid); setShowModal(false) }}
          onAddServer={() => {}}
        />
      )}

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
