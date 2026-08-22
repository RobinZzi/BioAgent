import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Environment } from '../types'
import { useI18n } from '../i18n'

export default function NewProjectModal({
  onClose, onCreate, onAddServer,
}: {
  onClose: () => void
  onCreate: (name: string, category: 'local' | 'remote', workdir: string, serverId: string) => void
  onAddServer: (env: Environment) => void
}) {
  const { t } = useI18n()
  const [name, setName] = useState('')
  const [category, setCategory] = useState<'local' | 'remote'>('local')
  const [servers, setServers] = useState<Environment[]>([])
  const [serverId, setServerId] = useState('')
  const [serverWorkdir, setServerWorkdir] = useState('')
  const [workdir, setWorkdir] = useState('')
  const [showPicker, setShowPicker] = useState(false)
  const [showAddServer, setShowAddServer] = useState(false)

  useEffect(() => {
    api.servers().then((s) => {
      setServers(s)
      if (s[0]) setServerId(s[0].id)
    }).catch(console.error)
  }, [])

  const submit = () => {
    if (!name.trim()) return
    const wd = category === 'local' ? workdir : serverWorkdir
    onCreate(name.trim(), category, wd, category === 'remote' ? serverId : '')
  }

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="confirm-panel" style={{ width: 460 }} onClick={(e) => e.stopPropagation()}>
        <b>{t('createProject')}</b>
        <div style={{ marginTop: 14 }}>
          <input placeholder={t("projectName")} value={name}
                 onChange={(e) => setName(e.target.value)} autoFocus style={{ width: '100%' }} />
        </div>

        <div style={{ margin: '14px 0 10px' }}>
          <div className="muted" style={{ marginBottom: 6 }}>{t('projectCategory')}</div>
          <div className="mode-group">
            <button className={category === 'local' ? 'active' : ''} onClick={() => setCategory('local')}>{t('localProject')}</button>
            <button className={category === 'remote' ? 'active' : ''} onClick={() => setCategory('remote')}>{t('remoteProject')}</button>
          </div>
        </div>

        {category === 'local' && (
          <div style={{ marginBottom: 14 }}>
            <div className="muted" style={{ marginBottom: 6 }}>{t('workdir')}{t('workdirHint')}</div>
            <div className="flex">
              <input placeholder={t("workdir")} value={workdir}
                     onChange={(e) => setWorkdir(e.target.value)} style={{ flex: 1 }} />
              <button onClick={() => setShowPicker(!showPicker)}>{t('browse')}</button>
            </div>
            <div className="muted" style={{ marginTop: 4 }}>{t("browseHint")}</div>
            {showPicker && <DirPicker onPick={(p) => { setWorkdir(p); setShowPicker(false) }} />}
          </div>
        )}

        {category === 'remote' && (
          <div style={{ marginBottom: 14 }}>
            <div className="muted" style={{ marginBottom: 6 }}>{t('server')}</div>
            <div className="flex">
              <select value={serverId} onChange={(e) => setServerId(e.target.value)} style={{ flex: 1 }}>
                <option value="">{t("selectServer")}</option>
                {servers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name || t('unnamedServer')}（{s.ssh_host || s.connector_url || 'Connector'}）
                  </option>
                ))}
              </select>
              <button onClick={() => setShowAddServer(!showAddServer)}>{t('addServer')}</button>
            </div>
            {showAddServer && <AddServerForm onAdded={(env) => { setServers([env, ...servers]); setServerId(env.id); setShowAddServer(false) }} />}
            <div className="muted" style={{ margin: '10px 0 6px' }}>{t('serverWorkdir')}</div>
            <input placeholder={t("serverWorkdirPlaceholder")} value={serverWorkdir}
                   onChange={(e) => setServerWorkdir(e.target.value)} style={{ width: '100%' }} />
          </div>
        )}

        <div className="flex" style={{ justifyContent: 'flex-end' }}>
          <button onClick={onClose}>{t('cancel')}</button>
          <button className="primary" onClick={submit} disabled={!name.trim() || (category === 'remote' && !serverId)}>{t('create')}</button>
        </div>
      </div>
    </div>
  )
}

function DirPicker({ onPick }: { onPick: (p: string) => void }) {
  const { t } = useI18n()
  const [cur, setCur] = useState('/Users/robin/Desktop')
  const [data, setData] = useState<{ path: string; parent: string; dirs: string[] } | null>(null)

  useEffect(() => { api.fsList(cur).then(setData).catch(console.error) }, [cur])

  return (
    <div className="dir-picker">
      <div className="flex" style={{ marginBottom: 8 }}>
        <span className="muted mono" style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>{data?.path ?? cur}</span>
        <button className="ghost" onClick={() => data && setCur(data.parent)}>{t('parent')}</button>
      </div>
      <div className="dir-list">
        {data?.dirs.map((d) => (
          <div key={d} className="dir-item" onClick={() => setCur(`${data.path}/${d}`)}>
            <span className="dir-icon" />{d}
          </div>
        ))}
        {data?.dirs.length === 0 && <div className="muted" style={{ padding: 8 }}>{t('noSubdir')}</div>}
      </div>
      <div className="flex" style={{ marginTop: 10, justifyContent: 'flex-end' }}>
        <button className="primary" onClick={() => onPick(data?.path ?? cur)}>{t('chooseDir')}</button>
      </div>
    </div>
  )
}

function AddServerForm({ onAdded }: { onAdded: (env: Environment) => void }) {
  const { t } = useI18n()
  const [mode, setMode] = useState<'ssh' | 'connector'>('ssh')
  const [form, setForm] = useState({ name: 'HPC', host: '', port: '22', user: '', password: '', key_path: '', connector_url: '', token: '' })
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setBusy(true)
    try {
      let env: Environment
      if (mode === 'ssh') {
        env = await api.registerSSHGlobal({
          name: form.name, host: form.host, port: parseInt(form.port) || 22,
          user: form.user, password: form.password, key_path: form.key_path,
        })
      } else {
        env = await api.registerRemoteGlobal({
          name: form.name, connector_url: form.connector_url, token: form.token,
        })
      }
      onAdded(env)
    } catch (e) { alert((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div className="card" style={{ marginTop: 8 }}>
      <div className="mode-group" style={{ marginBottom: 8 }}>
        <button className={mode === 'ssh' ? 'active' : ''} onClick={() => setMode('ssh')}>{t('sshServer')}</button>
        <button className={mode === 'connector' ? 'active' : ''} onClick={() => setMode('connector')}>Connector</button>
      </div>
      <div className="create-form">
        <input placeholder={t("serverName")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        {mode === 'ssh' ? (
          <>
            <input placeholder={t("serverHost")} value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} />
            <input placeholder={t("port")} value={form.port} style={{ width: 70 }} onChange={(e) => setForm({ ...form, port: e.target.value })} />
            <input placeholder={t("account")} value={form.user} onChange={(e) => setForm({ ...form, user: e.target.value })} />
            <input type="password" placeholder={t("password")} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </>
        ) : (
          <>
            <input placeholder={t("connectorUrl")} value={form.connector_url} onChange={(e) => setForm({ ...form, connector_url: e.target.value })} />
            <input placeholder={t("tokenPlaceholder")} value={form.token} onChange={(e) => setForm({ ...form, token: e.target.value })} />
          </>
        )}
        <button className="primary" onClick={submit} disabled={busy}>{busy ? t('connecting') : t('add')}</button>
      </div>
    </div>
  )
}
