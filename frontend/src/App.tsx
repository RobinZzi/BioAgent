import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import type { ConversationDetail, Project, ProjectDetail, Settings } from './types'
import TopBar from './components/TopBar'
import ProjectColumn from './components/ProjectColumn'
import ConversationColumn from './components/ConversationColumn'
import ResultColumn from './components/ResultColumn'
import SettingsPanel from './components/SettingsPanel'

export type ResultTab = 'dag' | 'artifacts' | 'datasets'

export default function App() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ProjectDetail | null>(null)
  const [conv, setConv] = useState<ConversationDetail | null>(null)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState<ResultTab>('dag')
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null)

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

      <div className="columns">
        <ProjectColumn
          projects={projects}
          currentId={projectId}
          onSelect={setProjectId}
          onCreate={createProject}
          onDelete={deleteProjects}
          onRefresh={refreshProjects}
        />

        <ConversationColumn
          convId={convObj?.id}
          messages={conv?.messages ?? []}
          busy={busy}
          onSendStart={() => setBusy(true)}
          onRefresh={refreshDetail}
        />

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
