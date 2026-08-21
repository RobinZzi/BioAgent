import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import type { ConversationDetail, Project, ProjectDetail, Settings } from './types'
import LoginPage from './components/LoginPage'
import TopBar from './components/TopBar'
import ProjectColumn from './components/ProjectColumn'
import ConversationColumn from './components/ConversationColumn'
import ResultColumn from './components/ResultColumn'
import SettingsPanel from './components/SettingsPanel'

export type ResultTab = 'dag' | 'artifacts' | 'datasets'

export default function App() {
  const [authed, setAuthed] = useState(false)
  const [authChecked, setAuthChecked] = useState(false)
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ProjectDetail | null>(null)
  const [conv, setConv] = useState<ConversationDetail | null>(null)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState<ResultTab>('dag')
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null)
  const [leftW, setLeftW] = useState(250)
  const [midW, setMidW] = useState(390)
  const resizing = useRef<'left' | 'mid' | null>(null)
  const [dragging, setDragging] = useState<'left' | 'mid' | null>(null)

  useEffect(() => {
    // 单机模式：无需 token 直接可用；认证模式：未登录则跳登录页
    api.listProjects()
      .then(() => { setAuthed(true); setAuthChecked(true) })
      .catch(() => { localStorage.removeItem('bioagent_token'); setAuthChecked(true) })
  }, [])

  const handleLogin = (token: string) => {
    localStorage.setItem('bioagent_token', token)
    setAuthed(true)
  }

  if (!authChecked) return null
  if (!authed) return <LoginPage onLogin={handleLogin} />

  const startResize = (e: React.MouseEvent, which: 'left' | 'mid') => {
    e.preventDefault()
    resizing.current = which
    setDragging(which)
    const startX = e.clientX
    const startLeft = leftW
    const startMid = midW
    const onMove = (ev: MouseEvent) => {
      const dx = ev.clientX - startX
      if (resizing.current === 'left') setLeftW(Math.max(180, Math.min(500, startLeft + dx)))
      else setMidW(Math.max(280, Math.min(600, startMid + dx)))
    }
    const onUp = () => {
      resizing.current = null
      setDragging(null)
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  const refreshProjects = useCallback(() => {
    api.listProjects().then(setProjects).catch(console.error)
  }, [])

  const refreshSettings = useCallback(() => {
    api.settings().then(setSettings).catch(console.error)
  }, [])

  const refreshDetail = useCallback(async () => {
    if (!projectId) return
    try {
      const d = await api.projectDetail(projectId)
      setDetail(d)
      const convId = d.conversations[0]?.id
      if (convId) setConv(await api.conversationDetail(convId))
    } catch (e) {
      console.error(e)
    }
  }, [projectId])

  useEffect(() => {
    refreshProjects()
    refreshSettings()
  }, [refreshProjects, refreshSettings])

  useEffect(() => {
    setDetail(null)
    setConv(null)
    setSelectedEventId(null)
    setTab('dag')
    refreshDetail()
  }, [projectId, refreshDetail])

  // 分析进行中轮询
  useEffect(() => {
    if (!busy || !projectId) return
    const started = Date.now()
    const timer = window.setInterval(async () => {
      try {
        const d = await api.projectDetail(projectId)
        setDetail(d)
        const convId = d.conversations[0]?.id
        if (convId) {
          const c = await api.conversationDetail(convId)
          setConv(c)
          const last = c.messages[c.messages.length - 1]
          const done = last && last.role === 'assistant' && !last.content.startsWith('分析执行中')
          if (done || Date.now() - started > 180000) {
            setBusy(false)
            refreshDetail()
          }
        }
      } catch { /* 网络抖动忽略 */ }
    }, 1500)
    return () => window.clearInterval(timer)
  }, [busy, projectId, refreshDetail])

  const createProject = async (name: string, category: 'local' | 'remote', workdir: string, serverId: string) => {
    const p = await api.createProject({
      name, data_source: category, compute_location: category,
      workdir, server_id: serverId,
    })
    await api.createConversation(p.id)
    refreshProjects()
    setProjectId(p.id)
  }

  const deleteProjects = async (ids: string[], deleteFiles: boolean) => {
    try {
      const r = await api.batchDeleteProjects(ids, deleteFiles)
      if (projectId && ids.includes(projectId)) {
        setProjectId(null)
        setDetail(null)
        setConv(null)
      }
      refreshProjects()
      alert(`已删除 ${r.deleted.length} 个项目${deleteFiles ? '（含文件）' : '（保留文件）'}`)
    } catch (e) { alert((e as Error).message) }
  }

  const switchEnv = async (envId: string) => {
    const convId = conv?.conversation.id
    if (!convId) return
    try {
      await api.setConversationEnvironment(convId, envId)
      refreshDetail()
    } catch (e) { alert((e as Error).message) }
  }

  const convObj = conv?.conversation ?? detail?.conversations[0]

  return (
    <div className="app">
      <TopBar
        project={detail?.project}
        conversation={convObj}
        environments={detail?.environments ?? []}
        agentStatus={settings?.agent_status}
        onSwitchEnv={switchEnv}
        onOpenSettings={() => setShowSettings(true)}
        onRefresh={refreshDetail}
      />

      <div className="columns" style={{ userSelect: dragging ? 'none' : undefined }}>
        <div className="col-wrap fixed" style={{ width: leftW }}>
          <ProjectColumn
            projects={projects}
            currentId={projectId}
            onSelect={setProjectId}
            onCreate={createProject}
            onDelete={deleteProjects}
            onRefresh={refreshProjects}
          />
        </div>
        <div className={`resizer ${dragging === 'left' ? 'dragging' : ''}`} onMouseDown={(e) => startResize(e, 'left')} />

        <div className="col-wrap fixed" style={{ width: midW }}>
          <ConversationColumn
            convId={convObj?.id}
            messages={conv?.messages ?? []}
            busy={busy}
            onSendStart={() => setBusy(true)}
            onRefresh={refreshDetail}
          />
        </div>
        <div className={`resizer ${dragging === 'mid' ? 'dragging' : ''}`} onMouseDown={(e) => startResize(e, 'mid')} />

        <div className="col-wrap main">
          <ResultColumn
            detail={detail}
            convId={convObj?.id}
            tab={tab}
            setTab={setTab}
            selectedEventId={selectedEventId}
            setSelectedEventId={setSelectedEventId}
            onRefresh={refreshDetail}
          />
        </div>
      </div>

      {showSettings && (
        <SettingsPanel
          settings={settings}
          environments={detail?.environments ?? []}
          projectId={projectId}
          onClose={() => setShowSettings(false)}
          onRefreshSettings={refreshSettings}
          onRefreshDetail={refreshDetail}
        />
      )}
    </div>
  )
}
