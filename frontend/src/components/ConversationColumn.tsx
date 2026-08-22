import { useState } from 'react'
import { api } from '../api'
import { useI18n } from '../i18n'
import type { Message } from '../types'

const QUICK = [
  ['fullAnalysis', '做完整分析'],
  ['dataCheck', '帮我看看这个数据质量'],
  ['QC', 'QC'],
  ['clustering', '聚类，分辨率 0.5'],
  ['annotation', '注释细胞类型'],
  ['UMAP', 'umap'],
  ['deAnalysis', '差异表达'],
  ['continue', '继续'],
]

export default function ConversationColumn({
  convId, messages, busy, onSendStart, onRefresh,
}: {
  convId?: string
  messages: Message[]
  busy: boolean
  onSendStart: () => void
  onRefresh: () => void
}) {
  const { t } = useI18n()
  const [text, setText] = useState('')

  const send = async (content: string) => {
    if (!convId || !content.trim() || busy) return
    setText('')
    onSendStart()
    try {
      await api.sendMessage(convId, content.trim(), false)
    } catch (e) {
      alert((e as Error).message)
      onRefresh()
    }
  }

  return (
    <div className="col">
      <div className="col-header">
        <span>{t('conversation')}</span>
        <span className="muted mono" style={{ marginLeft: 'auto' }}>{convId?.slice(0, 12) ?? ''}</span>
      </div>

      <div className="conv-messages">
        {messages.length === 0 && (
          <div className="empty">
            {t('noMessages')}
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`msg ${m.role}`}>
            {m.content}
            <span className="ts">{new Date(m.created_at ?? '').toLocaleTimeString()}</span>
          </div>
        ))}
        {busy && (
          <div className="msg assistant">
            {t('analyzing')}
          </div>
        )}
      </div>

      <div className="quick-actions">
        {QUICK.map(([label, phrase]) => (
          <button key={label} disabled={busy} onClick={() => send(phrase)}>{t(label)}</button>
        ))}
      </div>

      <div className="conv-input">
        <textarea
          placeholder={t('inputPlaceholder')}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(text) }
          }}
        />
        <button className="primary" disabled={busy || !text.trim()} onClick={() => send(text)}>{t('send')}</button>
      </div>
    </div>
  )
}
