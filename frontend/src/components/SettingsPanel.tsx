import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Capability, Environment, ResolveResult, Settings } from '../types'

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
      alert(`${r.ok ? '连通正常' : '不可用'}：${r.detail}`)
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
          <span>设置</span>
          <span className="muted">工作模式 · Agent · 环境 · API</span>
          <span className="spacer" />
          <button className="ghost" onClick={onClose}>关闭</button>
        </div>

        <div className="settings-body">
          <div className="settings-section">
            <h4>工作模式（执行器）</h4>
            <div className="mode-group">
              {EXECUTOR_MODES.map((m) => (
                <button key={m.id} title={m.desc}
                        className={settings?.executor_mode === m.id ? 'active' : ''}
                        onClick={() => patch({ executor_mode: m.id })}>
                  {m.label}
                </button>
              ))}
            </div>
            <div className="muted" style={{ marginTop: 6 }}>
              当前：{settings?.executor_mode ?? '—'}
            </div>
          </div>

          <div className="settings-section">
            <h4>Agent 模式</h4>
            <div className="mode-group">
              {LLM_MODES.map((m) => (
                <button key={m.id} title={m.desc}
                        className={settings?.llm_mode === m.id ? 'active' : ''}
                        onClick={() => patch({ llm_mode: m.id })}>
                  {m.label}
                </button>
              ))}
            </div>
            <div className="muted" style={{ marginTop: 6 }}>
              当前：{settings?.llm_mode ?? '—'}
              {settings?.llm_mode === 'real' && settings?.llm_configured === false &&
                ' · 未配置 API Key，real 模式需先设置 API Key'}
            </div>
          </div>

          <div className="settings-section">
            <h4>LLM API Key</h4>
            <div className="muted" style={{ marginBottom: 8 }}>
              配置 OpenAI 兼容 API（默认 DeepSeek）。Key 仅保存在本机后端数据目录，不会返回前端明文。
              状态：{settings?.llm_configured ? '已配置' : '未配置'}
            </div>
            <div className="create-form">
              <input type="password" placeholder="API Key（sk-...）" value={apiKey}
                     onChange={(e) => setApiKey(e.target.value)}
                     style={{ minWidth: 220 }} />
              <input placeholder="Base URL" value={baseUrl}
                     onChange={(e) => setBaseUrl(e.target.value)}
                     style={{ minWidth: 200 }} />
              <input placeholder="模型" value={model}
                     onChange={(e) => setModel(e.target.value)} />
              <button className="primary" onClick={saveApiKey} disabled={savingKey || !apiKey.trim()}>
                保存
              </button>
              {settings?.llm_configured && (
                <button onClick={clearApiKey} disabled={savingKey}>清除</button>
              )}
            </div>
            <div className="muted" style={{ marginTop: 6 }}>
              当前：{settings?.llm_model ?? '—'} · {settings?.llm_base_url ?? '—'}
            </div>
          </div>

          <div className="settings-section">
            <h4>计算环境</h4>
            <div className="flex" style={{ marginBottom: 10 }}>
              <button className="primary" onClick={discover} disabled={busy || !projectId}>
                {busy ? '发现中…' : '本机环境发现'}
              </button>
              <button onClick={() => { setShowRemoteForm(!showRemoteForm); setShowSSHForm(false) }}>
                {showRemoteForm ? '取消' : '注册 Connector'}
              </button>
              <button onClick={() => { setShowSSHForm(!showSSHForm); setShowRemoteForm(false) }}>
                {showSSHForm ? '取消' : '注册 SSH 服务器'}
              </button>
            </div>

            {showRemoteForm && (
              <div className="card" style={{ marginBottom: 10 }}>
                <div className="create-form">
                  <input placeholder="环境名（如 Lab HPC）" value={remote.name}
                         onChange={(e) => setRemote({ ...remote, name: e.target.value })} />
                  <input placeholder="Connector 地址" value={remote.connector_url}
                         onChange={(e) => setRemote({ ...remote, connector_url: e.target.value })} />
                  <input placeholder="共享令牌" value={remote.token}
                         onChange={(e) => setRemote({ ...remote, token: e.target.value })} />
                  <button className="primary" onClick={registerRemote} disabled={busy}>注册并握手</button>
                </div>
                <div className="muted" style={{ marginTop: 6 }}>令牌仅用于 Connector 调用鉴权，非 SSH 凭据。</div>
              </div>
            )}

            {showSSHForm && (
              <div className="card" style={{ marginBottom: 10 }}>
                <div className="create-form">
                  <input placeholder="环境名（如 Lab HPC）" value={ssh.name}
                         onChange={(e) => setSSH({ ...ssh, name: e.target.value })} />
                  <input placeholder="服务器地址（host）" value={ssh.host}
                         onChange={(e) => setSSH({ ...ssh, host: e.target.value })} />
                  <input placeholder="端口" value={ssh.port} style={{ width: 70 }}
                         onChange={(e) => setSSH({ ...ssh, port: e.target.value })} />
                  <input placeholder="账号" value={ssh.user}
                         onChange={(e) => setSSH({ ...ssh, user: e.target.value })} />
                  <input type="password" placeholder="密码（或留空用密钥）" value={ssh.password}
                         onChange={(e) => setSSH({ ...ssh, password: e.target.value })} />
                  <input placeholder="私钥路径（可选）" value={ssh.key_path}
                         onChange={(e) => setSSH({ ...ssh, key_path: e.target.value })} />
                  <button className="primary" onClick={registerSSH} disabled={busy}>注册</button>
                </div>
                <div className="muted" style={{ marginTop: 6 }}>
                  密码加密存储于本机后端，接口不回显明文。注册时会做一次连接测试（失败仍保存，标记不可用）。
                </div>
              </div>
            )}

            {environments.map((env) => (
              <div key={env.id} className="card" style={{ marginBottom: 10 }}>
                <div className="flex">
                  <b>{env.name}</b>
                  <span className={`badge ${env.status === 'healthy' ? 'green' : 'amber'}`}>{env.status}</span>
                  <span className="badge gray">{env.env_type === 'remote' ? (env.ssh_host ? 'SSH' : '远程') : '本地'}</span>
                  <span className="spacer" />
                  <button onClick={() => testEnv(env.id)} disabled={testing === env.id}>
                    {testing === env.id ? '测试中' : '测试'}
                  </button>
                </div>
                {env.connector_url && <div className="muted mono" style={{ marginTop: 4 }}>{env.connector_url}</div>}
                {env.ssh_host && (
                  <div className="muted mono" style={{ marginTop: 4 }}>
                    {env.ssh_user}@{env.ssh_host}:{env.ssh_port}
                    {env.ssh_has_password ? ' · 密码已配置' : env.ssh_key_path ? ' · 密钥已配置' : ' · 未配置凭据'}
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
            <h4>能力解析（Tool → Capability）</h4>
            <div className="flex">
              <select value={selCap} onChange={(e) => setSelCap(e.target.value)} style={{ flex: 1 }}>
                {caps.map((c) => (
                  <option key={c.capability_id} value={c.capability_id}>
                    {c.domain} · {c.name}
                  </option>
                ))}
              </select>
              <button onClick={doResolve}>解析</button>
            </div>
            {resolve && (
              <div style={{ marginTop: 8 }}>
                {resolve.implementations.map((i) => (
                  <div key={i.id} className="resolve-row">
                    <span className={`badge ${i.available ? 'green' : 'red'}`}>
                      {i.available ? '可用' : '不可用'}
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
            <h4>系统</h4>
            <div className="muted">
              认证模式：{settings?.auth_enabled
                ? '已开启（注册/登录，适合共享服务器部署）'
                : '单机模式（免登录，个人本机使用）'}
              <div style={{ marginTop: 4 }}>切换需设置 BIOAGENT_AUTH_ENABLED=true 并重启后端。</div>
            </div>
          </div>

          <div className="settings-section">
            <h4>API</h4>
            <div className="muted">
              接口文档：<a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">Swagger UI</a> ·
              <a href="http://127.0.0.1:8000/api/health" target="_blank" rel="noreferrer"> health</a>
              <div style={{ marginTop: 4 }}>版本 {settings?.version ?? '—'}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
