import { useState } from 'react'
import { api } from '../api'
import type { Message } from '../types'

const QUICK = [
  ['数据检查', '帮我看看这个数据质量'],
  ['QC', 'QC'],
  ['聚类', '聚类，分辨率 0.5'],
  ['注释', '注释细胞类型'],
  ['UMAP', 'umap'],
  ['差异表达', '差异表达'],
  ['继续', '继续'],
]

export default function ConversationPanel({
  convId, messages, busy, onSendStart, onRefresh,
}: {
  convId?: string
  messages: Message[]
  busy: boolean
  onSendStart: () => void
  onRefresh: () => void
}) {
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
    <div className="conv-panel">
      <div className="conv-header">
        <span>💬</span>
        <span style={{ fontWeight: 600 }}>{convId ? '分析对话' : '对话'}</span>
        <span className="muted mono" style={{ marginLeft: 'auto' }}>{convId ?? '未创建'}</span>
      </div>

      <div className="conv-messages">
        {messages.length === 0 && (
          <div className="empty">与 BioAgent 对话，用自然语言描述分析需求，例如「聚类，分辨率 1.0」。</div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`msg ${m.role}`}>
            {m.content}
            <span className="ts">{new Date(m.created_at ?? '').toLocaleTimeString()}</span>
          </div>
        ))}
        {busy && (
          <div className="msg assistant">
            <span className="spin">⏳</span> 分析执行中，可在右侧 DAG 面板查看事件进度…
          </div>
        )}
      </div>

      <div className="quick-actions">
        {QUICK.map(([label, phrase]) => (
          <button key={label} disabled={busy} onClick={() => send(phrase)}>{label}</button>
        ))}
      </div>

      <div className="conv-input">
        <textarea
          placeholder="描述你的分析需求…（v0.1 规则引擎：QC / 聚类 / 注释 / UMAP / 差异表达 / 继续）"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(text) } }}
        />
        <button className="primary" disabled={busy || !text.trim()} onClick={() => send(text)}>发送</button>
      </div>
    </div>
  )
}
