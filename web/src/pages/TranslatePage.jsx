import { useState } from 'react'
import { api } from '../api/client'
import { Languages, ArrowRight } from 'lucide-react'

export default function TranslatePage() {
  const [source, setSource] = useState('')
  const [result, setResult] = useState('')
  const [srcLang, setSrcLang] = useState('auto')
  const [tgtLang, setTgtLang] = useState('en')
  const [loading, setLoading] = useState(false)

  const LANGS = { auto: 'Auto', zh: 'Chinese', en: 'English', ja: 'Japanese', ko: 'Korean',
    fr: 'French', de: 'German', es: 'Spanish', ru: 'Russian', ar: 'Arabic', pt: 'Portuguese' }

  const translate = async () => {
    if (!source.trim()) return
    setLoading(true)
    const data = await api.post('/translate', { text: source, source: srcLang, target: tgtLang })
    setResult(data.translated || data.error || '')
    setLoading(false)
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-xl font-bold flex items-center gap-2">
        <Languages className="w-6 h-6 text-primary" /> Translator
      </h1>

      <div className="flex gap-3 items-center">
        <select value={srcLang} onChange={(e) => setSrcLang(e.target.value)}
          className="bg-bg-card border border-border rounded-lg px-3 py-2 text-sm">
          {Object.entries(LANGS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <ArrowRight className="w-4 h-4 text-text-secondary" />
        <select value={tgtLang} onChange={(e) => setTgtLang(e.target.value)}
          className="bg-bg-card border border-border rounded-lg px-3 py-2 text-sm">
          {Object.entries(LANGS).filter(([k]) => k !== 'auto').map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <button onClick={translate} disabled={loading}
          className="bg-primary text-white text-sm px-4 py-2 rounded-lg disabled:opacity-50">
          {loading ? 'Translating...' : 'Translate'}
        </button>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <textarea value={source} onChange={(e) => setSource(e.target.value)}
          placeholder="Enter text to translate..."
          rows={8}
          className="bg-bg-card border border-border rounded-xl p-4 text-sm resize-none focus:outline-none focus:border-primary" />
        <div className="bg-bg-card border border-border rounded-xl p-4 text-sm min-h-[200px] whitespace-pre-wrap">
          {result || <span className="text-text-secondary">Translation will appear here</span>}
        </div>
      </div>
    </div>
  )
}
