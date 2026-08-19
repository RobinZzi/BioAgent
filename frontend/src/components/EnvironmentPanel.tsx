import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Capability, Environment, ResolveResult } from '../types'

export default function EnvironmentPanel({
  projectId, environments, onRefresh,
}: {
  projectId: string
  environments: Environment[]
  onRefresh: () => void
}) {
  const [caps, setCaps] = useState<Capability[]>([])
  const [selCap, setSelCap] = useState('scrna.clustering')
  const [resolve, setResolve] = useState<ResolveResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [showRemoteForm, setShowRemoteForm] = useState(false)
  const [remote, setRemote] = useState({ name: '', connector_url: '', token: '' })
  const [testing, setTesting] = useState<string | null>(null)

  useEffect(() => {
    api.capabilities().then(setCaps).catch(console.error)
  }, [])

  const discover = async () => {
    setBusy(true)
    try {
      await api.discoverEnvironment(projectId)
      onRefresh()
    } catch (e) { alert((e as Error).message) } finally { setBusy(false) }
  }

  const registerRemote = async () => {
    if (!remote.name.trim() || !remote.connector_url.trim()) return
    setBusy(true)
    try {
      await api.registerRemoteEnvironment(projectId, {
        name: remote.name.trim(),
        connector_url: remote.connector_url.trim(),
        token: remote.token.trim(),
      })
      setShowRemoteForm(false)
      setRemote({ name: '', connector_url: '', token: '' })
      onRefresh()
    } catch (e) { alert((e as Error).message) } finally { setBusy(false) }
  }

  const testEnv = async (envId: string) => {
    setTesting(envId)
    try {
      const r = await api.testEnvironment(envId)
      alert(`${r.ok ? '✅' : '❌'} ${r.detail}`)
    } catch (e) { alert((e as Error).message) } finally { setTesting(null) }
  }

  const doResolve = async () => {
    const env = environments[0]
    const r = await api.resolve(selCap, env?.id)
    setResolve(r)
  }

  return (
    <div>
      <div className="flex" style={{ marginBottom: 14 }}>
        <button className="primary" onClick={discover} disabled={busy}>
          {busy ? '处理中…' : '🔍 环境发现'}
        </button>
        <button onClick={() => setShowRemoteForm(!showRemoteForm)}>
          {showRemoteForm ? '取消' : '🔗 注册远程 Connector'}
        </button>
        <span className="muted">
          本地：受控扫描生成 Manifest；远程：Local Connector 协议（Agent 不持有 SSH 凭据）。
        </span>
      </div>

      {showRemoteForm && (
        <div className="card" style={{ marginBottom: 14 }}>
          <b>注册远程计算环境（Local Connector）</b>
          <div className="create-form">
            <input placeholder="环境名（如 Lab HPC）" value={remote.name}
                   onChange={(e) => setRemote({ ...remote, name: e.target.value })} />
            <input placeholder="Connector 地址（如 http://10.0.0.5:8765）" value={remote.connector_url}
                   onChange={(e) => setRemote({ ...remote, connector_url: e.target.value })}
                   style={{ minWidth: 260 }} />
            <input placeholder="共享令牌（由 Connector 部署者提供）" value={remote.token}
                   onChange={(e) => setRemote({ ...remote, token: e.target.value })} />
            <button className="primary" onClick={registerRemote} disabled={busy}>注册并握手</button>
          </div>
          <div className="muted" style={{ marginTop: 6 }}>
            注册时执行 /discover 握手获取远程 Manifest；令牌不是 SSH 凭据，仅用于 Connector 调用鉴权。
          </div>
        </div>
      )}

      {environments.map((env) => (
        <div key={env.id} className="card" style={{ marginBottom: 14 }}>
          <div className="flex">
            <b>{env.env_type === 'remote' ? '🔗' : '🖥️'} {env.name}</b>
            <span className={`badge ${env.status === 'healthy' ? 'green' : 'amber'}`}>{env.status}</span>
            <span className="badge gray">{env.env_type === 'remote' ? '远程 Connector' : '本地'}</span>
            <span className="muted mono">{env.id}</span>
            <span className="spacer" style={{ flex: 1 }} />
            <button onClick={() => testEnv(env.id)} disabled={testing === env.id}>
              {testing === env.id ? '测试中…' : '测试连通性'}
            </button>
            <button onClick={async () => {
              if (env.env_type === 'remote') {
                alert('远程环境由其 Connector 自行发现；请重启 Connector 或在该机器上执行环境发现。')
                return
              }
              await api.rediscoverEnvironment(env.id); onRefresh()
            }}>
              重新发现
            </button>
          </div>
          {env.connector_url && <div className="muted mono" style={{ marginTop: 4 }}>connector: {env.connector_url}</div>}
          <details style={{ marginTop: 10 }}>
            <summary className="muted" style={{ cursor: 'pointer' }}>查看 Environment Manifest（runtimes / tools / compute）</summary>
            <pre className="env-manifest">{JSON.stringify(env.manifest, null, 2)}</pre>
          </details>
        </div>
      ))}

      <div className="card">
        <b>🧩 Capability Resolver</b>
        <div className="muted" style={{ margin: '4px 0 10px' }}>
          Tool ≠ Capability：这里把「环境里装了什么」解析为「能完成什么分析意图」。
        </div>
        <div className="flex">
          <select value={selCap} onChange={(e) => setSelCap(e.target.value)} style={{ minWidth: 260 }}>
            {caps.map((c) => (
              <option key={c.capability_id} value={c.capability_id}>
                {c.domain} · {c.name} ({c.capability_id})
              </option>
            ))}
          </select>
          <button onClick={doResolve}>解析</button>
        </div>
        {resolve && (
          <div style={{ marginTop: 12 }}>
            <div className="muted" style={{ marginBottom: 4 }}>{resolve.capability_id} 可用实现：</div>
            {resolve.implementations.map((i) => (
              <div key={i.id} className="resolve-row">
                <span className={`badge ${i.available ? 'green' : 'red'}`}>
                  {i.available ? '✓ 可用' : '✕ 不可用'}
                </span>
                <span className="mono">{i.id}</span>
                <span className="muted">({i.language})</span>
                {i.runtime_id && <span className="muted mono">@{i.runtime_id}</span>}
                {i.reason && <span className="muted" style={{ marginLeft: 'auto' }}>{i.reason}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
