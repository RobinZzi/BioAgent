import { useState } from 'react'
import { api } from '../api'
import { useI18n } from '../i18n'

export default function LoginPage({ onLogin }: { onLogin: (token: string, username: string) => void }) {
  const { t } = useI18n()
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
          <p className="muted">{t('loginTitle')}</p>
        </div>
        <div className="mode-group" style={{ justifyContent: 'center', marginBottom: 16 }}>
          <button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>{t('login')}</button>
          <button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>{t('register')}</button>
        </div>
        <input placeholder={t("username")} value={username} onChange={(e) => setUsername(e.target.value)}
               style={{ width: '100%', marginBottom: 10 }} autoFocus />
        <input type="password" placeholder={t("password")} value={password} onChange={(e) => setPassword(e.target.value)}
               style={{ width: '100%', marginBottom: 12 }}
               onKeyDown={(e) => { if (e.key === 'Enter') submit() }} />
        {error && <div className="login-error">{error}</div>}
        <button className="primary" style={{ width: '100%' }} onClick={submit} disabled={busy || !username.trim() || !password}>
          {busy ? '…' : mode === 'login' ? t('login') : t('register')}
        </button>
        {mode === 'register' && (
          <div className="muted" style={{ marginTop: 10, textAlign: 'center' }}>{t('firstAdmin')}</div>
        )}
      </div>
    </div>
  )
}
