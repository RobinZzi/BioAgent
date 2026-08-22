import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Capability, Environment, ResolveResult, Settings } from '../types'
import { useI18n } from '../i18n'

const EXECUTOR_MODES = [
  { id: 'mock', label: 'mock', desc: '预生成合理产物，无生信环境也能完整演示' },
  { id: 'auto', label: 'auto', desc: '逐个探测 runtime，真实执行，失败回退 mock（推荐）' },
  { id: 'local', label: 'local', desc: '只走真实执行，工具缺失即结构化失败' },
]

const LLM_MODES = [
  { id: 'off', label: 'off', desc: '规则引擎，无需配置' },
  { id: 'echo', label: 'echo', desc: '模拟 LLM 返回，验证集成链路' },
  { id: 'real', label: 'real', desc: 'OpenAI 兼容 API（需配置 Key）' },
]

export default function SettingsPanel({
  settings, environments, projectId, onClose, onRefreshSettings, onRefreshDetail,
}: {
  settings: Settings | null
  environments: Environment[]
  projectId: string | null
  onClose: () => void
  onRefreshSettings: () => void
  onRefreshDetail: () => void
}) {
  const { t } = useI18n()
  const [caps, setCaps] = useState<Capability[]>([])
  const [selCap, setSelCap] = useState('scrna.clustering')
  const [resolve, setResolve] = useState<ResolveResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [showRemoteForm, setShowRemoteForm] = useState(false)
  const [showSSHForm, setShowSSHForm] = useState(false)
  const [remote, setRemote] = useState({ name: '', connector_url: '', token: '' })
  const [ssh, setSSH] = useState({ name: '', host: '', port: '22', user: '', password: '', key_path: '' })
  const [testing, setTesting] = useState<string | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState(settings?.llm_base_url ?? '')
  const [model, setModel] = useState(settings?.llm_model ?? '')
  const [savingKey, setSavingKey] = useState(false)

  useEffect(() => {
    api.capabilities().then(setCaps).catch(console.error)
  }, [])

  const patch = async (body: { executor_mode?: string; llm_mode?: string }) => {
    try {
      await api.patchSettings(body)
      onRefreshSettings()
    } catch (e) { alert((e as Error).message) }
  }

  const saveApiKey = async () => {
    setSavingKey(true)
    try {
      await api.patchSettings({
        llm_api_key: apiKey,
        llm_base_url: baseUrl || undefined,
        llm_model: model || undefined,
      })
      setApiKey('')
      onRefreshSettings()
    } catch (e) { alert((e as Error).message) } finally { setSavingKey(false) }
  }

  const clearApiKey = async () => {
    setSavingKey(true)
    try {
      await api.patchSettings({ llm_api_key: '' })
      onRefreshSettings()
    } catch (e) { alert((e as Error).message) } finally { setSavingKey(false) }
  }

  const discover = async () => {
    if (!projectId) return
    setBusy(true)
    try {
      await api.discoverEnvironment(projectId)
      onRefreshDetail()
    } catch (e) { alert((e as Error).message) } finally { setBusy(false) }
  }

  const registerRemote = async () => {
    if (!projectId || !remote.name.trim() || !remote.connector_url.trim()) return
    setBusy(true)
    try {
      await api.registerRemoteEnvironment(projectId, {
        name: remote.name.trim(), connector_url: remote.connector_url.trim(), token: remote.token.trim(),
      })
      setShowRemoteForm(false)
      setRemote({ name: '', connector_url: '', token: '' })
      onRefreshDetail()
    } catch (e) { alert((e as Error).message) } finally { setBusy(false) }
  }

  const registerSSH = async () => {
    if (!projectId || !ssh.name.trim() || !ssh.host.trim() || !ssh.user.trim()) return
    setBusy(true)
    try {
      await api.registerSSHEnvironment(projectId, {
        name: ssh.name.trim(), host: ssh.host.trim(), port: parseInt(ssh.port) || 22,
        user: ssh.user.trim(), password: ssh.password, key_path: ssh.key_path.trim(),
      })
      setShowSSHForm(false)
      setSSH({ name: '', host: '', port: '22', user: '', password: '', key_path: '' })
      onRefreshDetail()
    } catch (e) { alert((e as Error).message) } finally { setBusy(false) }
  }

  const testEnv = async (envId: string) => {
    setTesting(envId)
    try {
      const r = await api.testEnvironment(envId)
      alert(`${r.ok ? t('testOk') : t('testBad')}：${r.detail}`)
    } catch (e) { alert((e as Error).message) } finally { setTesting(null) }
  }

  const doResolve = async () => {
    const env = environments[0]
    const r = await api.resolve(selCap, env?.id)
    setResolve(r)
  }

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-panel" onClick={(e) => e.stopPropagation()}>
        <div className="settings-header">
          <span>{t('settings')}</span>
          <span className="muted">{t('settingsSubtitle')}</span>
          <span className="spacer" />
          <button className="ghost" onClick={onClose}>{t('close')}</button>
        </div>

        <div className="settings-body">
          <div className="settings-section">
            <h4>{t('workMode')}</h4>
            <div className="mode-group">
              {EXECUTOR_MODES.map((m) => (
                <button key={m.id} title={t(m.id + 'Desc')}
                        className={settings?.executor_mode === m.id ? 'active' : ''}
                        onClick={() => patch({ executor_mode: m.id })}>
                  {m.label}
                </button>
              ))}
            </div>
            <div className="muted" style={{ marginTop: 6 }}>
              {t('current')}{settings?.executor_mode ?? '—'}
            </div>
          </div>

          <div className="settings-section">
            <h4>{t('agentMode')}</h4>
            <div className="mode-group">
              {LLM_MODES.map((m) => (
                <button key={m.id} title={t(m.id + 'Desc')}
                        className={settings?.llm_mode === m.id ? 'active' : ''}
                        onClick={() => patch({ llm_mode: m.id })}>
                  {m.label}
                </button>
              ))}
            </div>
            <div className="muted" style={{ marginTop: 6 }}>
              {t('current')}{settings?.llm_mode ?? '—'}
              {settings?.llm_mode === 'real' && settings?.llm_configured === false &&
                ' · ' + t('notConfiguredKeyNote')}
            </div>
          </div>

          <div className="settings-section">
            <h4>{t('llmApiKey')}</h4>
            <div className="muted" style={{ marginBottom: 8 }}>
              {t('apiKeyDesc')}
              {t('statusConfigured')}: {settings?.llm_configured ? t('statusConfigured') : t('statusNotConfigured')}
            </div>
            <div className="create-form">
              <input type="password" placeholder="API Key（sk-...）" value={apiKey}
                     onChange={(e) => setApiKey(e.target.value)}
                     style={{ minWidth: 220 }} />
              <input placeholder="Base URL" value={baseUrl}
                     onChange={(e) => setBaseUrl(e.target.value)}
                     style={{ minWidth: 200 }} />
              <input placeholder={t('modelPlaceholder')} value={model}
                     onChange={(e) => setModel(e.target.value)} />
              <button className="primary" onClick={saveApiKey} disabled={savingKey || !apiKey.trim()}>
                {t('save')}
              </button>
              {settings?.llm_configured && (
                <button onClick={clearApiKey} disabled={savingKey}>{t('clear')}</button>
              )}
            </div>
            <div className="muted" style={{ marginTop: 6 }}>
              {t('current')}{settings?.llm_model ?? '—'} · {settings?.llm_base_url ?? '—'}
            </div>
          </div>

          <div className="settings-section">
            <h4>{t('computeEnv')}</h4>
            <div className="flex" style={{ marginBottom: 10 }}>
              <button className="primary" onClick={discover} disabled={busy || !projectId}>
                {busy ? t('discovering') : t('discoverLocal')}
              </button>
              <button onClick={() => { setShowRemoteForm(!showRemoteForm); setShowSSHForm(false) }}>
                {showRemoteForm ? t('cancel') : t('registerConnector')}
              </button>
              <button onClick={() => { setShowSSHForm(!showSSHForm); setShowRemoteForm(false) }}>
                {showSSHForm ? t('cancel') : t('registerSSH')}
              </button>
            </div>

            {showRemoteForm && (
              <div className="card" style={{ marginBottom: 10 }}>
                <div className="create-form">
                  <input placeholder={t('envName')} value={remote.name}
                         onChange={(e) => setRemote({ ...remote, name: e.target.value })} />
                  <input placeholder={t('connectorUrl')} value={remote.connector_url}
                         onChange={(e) => setRemote({ ...remote, connector_url: e.target.value })} />
                  <input placeholder={t('tokenPlaceholder')} value={remote.token}
                         onChange={(e) => setRemote({ ...remote, token: e.target.value })} />
                  <button className="primary" onClick={registerRemote} disabled={busy}>{t('registerHandshake')}</button>
                </div>
                <div className="muted" style={{ marginTop: 6 }}>{t('tokenNote')}</div>
              </div>
            )}

            {showSSHForm && (
              <div className="card" style={{ marginBottom: 10 }}>
                <div className="create-form">
                  <input placeholder={t('envName')} value={ssh.name}
                         onChange={(e) => setSSH({ ...ssh, name: e.target.value })} />
                  <input placeholder={t('sshHostPlaceholder')} value={ssh.host}
                         onChange={(e) => setSSH({ ...ssh, host: e.target.value })} />
                  <input placeholder={t('portPlaceholder')} value={ssh.port} style={{ width: 70 }}
                         onChange={(e) => setSSH({ ...ssh, port: e.target.value })} />
                  <input placeholder={t('account')} value={ssh.user}
                         onChange={(e) => setSSH({ ...ssh, user: e.target.value })} />
                  <input type="password" placeholder={t('passwordOrKey')} value={ssh.password}
                         onChange={(e) => setSSH({ ...ssh, password: e.target.value })} />
                  <input placeholder={t('keyPathPlaceholder')} value={ssh.key_path}
                         onChange={(e) => setSSH({ ...ssh, key_path: e.target.value })} />
                  <button className="primary" onClick={registerSSH} disabled={busy}>{t('registerBtn')}</button>
                </div>
                <div className="muted" style={{ marginTop: 6 }}>
                  {t('sshNote')}
                </div>
              </div>
            )}

            {environments.map((env) => (
              <div key={env.id} className="card" style={{ marginBottom: 10 }}>
                <div className="flex">
                  <b>{env.name}</b>
                  <span className={`badge ${env.status === 'healthy' ? 'green' : 'amber'}`}>{env.status}</span>
                  <span className="badge gray">{env.env_type === 'remote' ? (env.ssh_host ? 'SSH' : t('remote')) : '本地'}</span>
                  <span className="spacer" />
                  <button onClick={() => testEnv(env.id)} disabled={testing === env.id}>
                    {testing === env.id ? t('testing') : t('testBtn')}
                  </button>
                </div>
                {env.connector_url && <div className="muted mono" style={{ marginTop: 4 }}>{env.connector_url}</div>}
                {env.ssh_host && (
                  <div className="muted mono" style={{ marginTop: 4 }}>
                    {env.ssh_user}@{env.ssh_host}:{env.ssh_port}
                    {env.ssh_has_password ? ' · ' + t('passwordConfigured') : env.ssh_key_path ? ' · ' + t('keyConfigured') : ' · ' + t('noCred')}
                  </div>
                )}
                <details style={{ marginTop: 8 }}>
                  <summary className="muted" style={{ cursor: 'pointer' }}>Manifest</summary>
                  <pre className="env-manifest">{JSON.stringify(env.manifest, null, 2)}</pre>
                </details>
              </div>
            ))}
          </div>

          <div className="settings-section">
            <h4>{t('capabilityResolve')}</h4>
            <div className="flex">
              <select value={selCap} onChange={(e) => setSelCap(e.target.value)} style={{ flex: 1 }}>
                {caps.map((c) => (
                  <option key={c.capability_id} value={c.capability_id}>
                    {c.domain} · {c.name}
                  </option>
                ))}
              </select>
              <button onClick={doResolve}>{t('resolveBtn')}</button>
            </div>
            {resolve && (
              <div style={{ marginTop: 8 }}>
                {resolve.implementations.map((i) => (
                  <div key={i.id} className="resolve-row">
                    <span className={`badge ${i.available ? 'green' : 'red'}`}>
                      {i.available ? t('available') : t('unavailable')}
                    </span>
                    <span className="mono">{i.id}</span>
                    <span className="muted">({i.language})</span>
                    {i.reason && <span className="muted" style={{ marginLeft: 'auto' }}>{i.reason}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="settings-section">
            <h4>{t('system')}</h4>
            <div className="muted">
              {t('authMode')}: {settings?.auth_enabled
                ? t('authOn')
                : t('authOff')}
              <div style={{ marginTop: 4 }}>{t('authSwitchNote')}</div>
            </div>
          </div>

          <div className="settings-section">
            <h4>{t('api')}</h4>
            <div className="muted">
              {t('apiDocs')}<a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">Swagger UI</a> ·
              <a href="http://127.0.0.1:8000/api/health" target="_blank" rel="noreferrer"> health</a>
              <div style={{ marginTop: 4 }}>{t('version')} {settings?.version ?? '—'}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
