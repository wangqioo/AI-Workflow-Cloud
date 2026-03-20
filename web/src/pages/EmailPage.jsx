import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { Mail, Send, Inbox } from 'lucide-react'

export default function EmailPage() {
  const [emails, setEmails] = useState([])
  const [selected, setSelected] = useState(null)
  const [showCompose, setShowCompose] = useState(false)
  const [form, setForm] = useState({ to: '', subject: '', body: '' })

  useEffect(() => {
    api.get('/email/inbox').then(d => setEmails(d.emails || []))
  }, [])

  const selectEmail = async (id) => {
    const email = await api.get(`/email/${id}`)
    setSelected(email)
  }

  const handleSend = async (e) => {
    e.preventDefault()
    await api.post('/email/send', form)
    setShowCompose(false)
    setForm({ to: '', subject: '', body: '' })
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <Mail className="w-6 h-6 text-primary" /> Email
        </h1>
        <button onClick={() => setShowCompose(!showCompose)}
          className="bg-primary text-white text-sm px-4 py-2 rounded-lg flex items-center gap-2">
          <Send className="w-4 h-4" /> Compose
        </button>
      </div>

      {showCompose && (
        <form onSubmit={handleSend} className="bg-bg-card border border-border rounded-xl p-4 space-y-3">
          <input value={form.to} onChange={(e) => setForm({ ...form, to: e.target.value })}
            placeholder="To" required className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary" />
          <input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })}
            placeholder="Subject" required className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary" />
          <textarea value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })}
            placeholder="Message" rows={4} className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary resize-none" />
          <button type="submit" className="bg-primary text-white text-sm px-4 py-2 rounded-lg">Send</button>
        </form>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-text-secondary flex items-center gap-1"><Inbox className="w-4 h-4" /> Inbox</h3>
          {emails.map(em => (
            <button key={em.id} onClick={() => selectEmail(em.id)}
              className={`w-full text-left bg-bg-card border rounded-lg p-3 ${selected?.id === em.id ? 'border-primary' : 'border-border'}`}>
              <div className="text-sm font-medium truncate">{em.subject}</div>
              <div className="text-xs text-text-secondary">{em.from} - {em.date}</div>
            </button>
          ))}
        </div>
        {selected && (
          <div className="bg-bg-card border border-border rounded-xl p-4">
            <h3 className="font-medium">{selected.subject}</h3>
            <div className="text-xs text-text-secondary mt-1">From: {selected.from} | {selected.date}</div>
            <div className="mt-3 text-sm whitespace-pre-wrap border-t border-border pt-3">{selected.body}</div>
          </div>
        )}
      </div>
    </div>
  )
}
