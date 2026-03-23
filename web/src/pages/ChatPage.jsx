import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { streamChat, api } from '../api/client'
import { Send, Bot, User, Loader2, Settings } from 'lucide-react'

export default function ChatPage() {
  const navigate = useNavigate()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [llmReady, setLlmReady] = useState(null)  // null=loading, true/false
  const endRef = useRef(null)
  const abortRef = useRef(null)

  useEffect(() => {
    api.get('/settings/llm').then(d => {
      setLlmReady(d.providers?.length > 0)
    }).catch(() => setLlmReady(false))
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    const text = input.trim()
    if (!text || streaming) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setStreaming(true)

    const assistantIdx = messages.length + 1
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])

    let accumulated = ''
    const cancel = streamChat(
      '/agents/stream',
      { message: text, session_id: sessionId },
      (chunk) => {
        accumulated += chunk
        setMessages(prev => {
          const updated = [...prev]
          updated[assistantIdx] = { role: 'assistant', content: accumulated }
          return updated
        })
      },
      () => setStreaming(false),
      (err) => {
        const errMsg = err?.includes('No LLM provider')
          ? '未配置 AI 模型，请前往「设置」页面配置 API Key。'
          : (accumulated || '连接失败，请检查 AI 模型配置后重试。')
        setMessages(prev => {
          const updated = [...prev]
          updated[assistantIdx] = { role: 'assistant', content: errMsg, isError: true }
          return updated
        })
        setStreaming(false)
      },
    )
    abortRef.current = cancel
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)] lg:h-[calc(100vh-3rem)] max-w-4xl mx-auto">
      <h1 className="text-xl font-bold mb-4">AI 助手</h1>

      {/* LLM 未配置提示横幅 */}
      {llmReady === false && (
        <div className="mb-4 flex items-center justify-between gap-3 bg-yellow-500/10 border border-yellow-500/30 rounded-xl px-4 py-3 text-sm text-yellow-400">
          <span>未配置 AI 模型，请先在「设置」页面添加 API Key</span>
          <button
            onClick={() => navigate('/settings')}
            className="flex items-center gap-1.5 text-xs bg-yellow-500/20 hover:bg-yellow-500/30 px-3 py-1.5 rounded-lg transition-colors whitespace-nowrap"
          >
            <Settings className="w-3.5 h-3.5" /> 去设置
          </button>
        </div>
      )}

      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.length === 0 && (
          <div className="text-center text-text-secondary mt-20">
            <Bot className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>开始和 AI 助手对话</p>
            <p className="text-sm mt-1">支持工具调用、RAG 知识库检索、工作流自动化</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center shrink-0 mt-0.5">
                <Bot className="w-4 h-4 text-primary" />
              </div>
            )}
            <div className={`
              max-w-[80%] rounded-xl px-4 py-2.5 text-sm leading-relaxed
              ${msg.role === 'user'
                ? 'bg-primary text-white'
                : msg.isError
                  ? 'bg-red-500/10 border border-red-500/30 text-red-400'
                  : 'bg-bg-card border border-border'}
            `}>
              <pre className="whitespace-pre-wrap font-sans m-0">{msg.content}</pre>
              {msg.role === 'assistant' && streaming && i === messages.length - 1 && !msg.isError && (
                <span className="inline-block w-1.5 h-4 bg-primary/60 animate-pulse ml-0.5" />
              )}
            </div>
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center shrink-0 mt-0.5">
                <User className="w-4 h-4 text-accent" />
              </div>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      {/* 输入框 */}
      <div className="mt-3 flex gap-2">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={llmReady === false ? '请先配置 AI 模型...' : '输入消息... (Enter 发送)'}
          disabled={llmReady === false}
          rows={1}
          className="flex-1 bg-bg-card border border-border rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:border-primary disabled:opacity-50 disabled:cursor-not-allowed"
        />
        <button
          onClick={sendMessage}
          disabled={streaming || !input.trim() || llmReady === false}
          className="bg-primary hover:bg-primary-dark text-white px-4 rounded-xl transition-colors disabled:opacity-40"
        >
          {streaming ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
        </button>
      </div>
    </div>
  )
}
