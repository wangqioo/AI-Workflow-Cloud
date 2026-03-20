import { useState, useRef, useEffect } from 'react'
import { streamChat } from '../api/client'
import { Send, Bot, User, Loader2 } from 'lucide-react'

export default function ChatPage() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const endRef = useRef(null)
  const abortRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    const text = input.trim()
    if (!text || streaming) return

    setInput('')
    const userMsg = { role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg])
    setStreaming(true)

    // Add empty assistant message for streaming
    const assistantIdx = messages.length + 1
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

    let accumulated = ''
    const cancel = streamChat(
      '/agents/stream',
      { message: text, session_id: sessionId },
      (chunk) => {
        accumulated += chunk
        setMessages((prev) => {
          const updated = [...prev]
          updated[assistantIdx] = { role: 'assistant', content: accumulated }
          return updated
        })
      },
      () => setStreaming(false),
      (err) => {
        console.error('Stream error:', err)
        setMessages((prev) => {
          const updated = [...prev]
          updated[assistantIdx] = {
            role: 'assistant',
            content: accumulated || 'Connection error. Please try again.',
          }
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
      <h1 className="text-xl font-bold mb-4">AI Assistant</h1>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.length === 0 && (
          <div className="text-center text-text-secondary mt-20">
            <Bot className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>Start a conversation with your AI assistant.</p>
            <p className="text-sm mt-1">Supports tool calling, RAG, and workflow automation.</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-primary" />
              </div>
            )}
            <div className={`
              max-w-[80%] rounded-xl px-4 py-2.5 text-sm leading-relaxed
              ${msg.role === 'user'
                ? 'bg-primary text-white'
                : 'bg-bg-card border border-border'}
            `}>
              <pre className="whitespace-pre-wrap font-sans m-0">{msg.content}</pre>
              {msg.role === 'assistant' && streaming && i === messages.length - 1 && (
                <span className="inline-block w-1.5 h-4 bg-primary/60 animate-pulse ml-0.5" />
              )}
            </div>
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center shrink-0">
                <User className="w-4 h-4 text-accent" />
              </div>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="mt-3 flex gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your message... (Enter to send)"
          rows={1}
          className="flex-1 bg-bg-card border border-border rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:border-primary"
        />
        <button
          onClick={sendMessage}
          disabled={streaming || !input.trim()}
          className="bg-primary hover:bg-primary-dark text-white px-4 rounded-xl transition-colors disabled:opacity-40"
        >
          {streaming ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
        </button>
      </div>
    </div>
  )
}
