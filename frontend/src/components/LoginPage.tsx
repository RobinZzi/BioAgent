import { useState } from 'react'
import { api } from '../api'

export default function LoginPage({ onLogin }: { onLogin: (token: string, username: string) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async () => {
    if (!username.trim() || !password) return
    setBusy(true)
    setError('')
    try {
      const r = mode === 'login'
        ? await api.login(username.trim(), password)
        : await api.register(username.trim(), password)
      onLogin(r.token, r.username)
    } catch (e) {
      setError((e as Error).message)
    } finally { setBusy(false) }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <img src="/logo.svg" alt="BioAgent" width="52" />
          <h1>BioAgent</h1>
          <p className="muted">生信分析 Agent 工作平台</p>
        </div>
        <div className="mode-group" style={{ justifyContent: 'center', marginBottom: 16 }}>
          <button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>登录</button>
          <button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>注册</button>
        </div>
        <input placeholder="用户名" value={username} onChange={(e) => setUsername(e.target.value)}
               style={{ width: '100%', marginBottom: 10 }} autoFocus />
        <input type="password" placeholder="密码" value={password} onChange={(e) => setPassword(e.target.value)}
               style={{ width: '100%', marginBottom: 12 }}
               onKeyDown={(e) => { if (e.key === 'Enter') submit() }} />
        {error && <div className="login-error">{error}</div>}
        <button className="primary" style={{ width: '100%' }} onClick={submit} disabled={busy || !username.trim() || !password}>
          {busy ? '处理中…' : mode === 'login' ? '登录' : '注册'}
        </button>
        {mode === 'register' && (
          <div className="muted" style={{ marginTop: 10, textAlign: 'center' }}>首个注册的用户将获得管理员权限</div>
        )}
      </div>
    </div>
  )
}
