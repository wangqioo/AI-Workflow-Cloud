import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { Database, Upload, Search, Trash2, FileText } from 'lucide-react'

export default function KnowledgePage() {
  const [docs, setDocs] = useState([])
  const [stats, setStats] = useState(null)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [uploading, setUploading] = useState(false)

  const loadDocs = () => {
    api.get('/rag/documents').then(d => setDocs(d.documents || []))
    api.get('/rag/stats').then(setStats)
  }
  useEffect(loadDocs, [])

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    const text = await file.text()
    await api.post('/rag/ingest', { content: text, filename: file.name })
    setUploading(false)
    loadDocs()
    e.target.value = ''
  }

  const handleSearch = async () => {
    if (!query.trim()) return
    const data = await api.post('/rag/query', { query, top_k: 5 })
    setResults(data.results || [])
  }

  const handleDelete = async (id) => {
    await api.delete(`/rag/documents/${id}`)
    loadDocs()
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <Database className="w-6 h-6 text-primary" /> Knowledge Base
        </h1>
        <label className="bg-primary hover:bg-primary-dark text-white text-sm px-4 py-2 rounded-lg cursor-pointer flex items-center gap-2">
          <Upload className="w-4 h-4" />
          {uploading ? 'Uploading...' : 'Upload Document'}
          <input type="file" className="hidden" onChange={handleUpload} accept=".txt,.md,.json,.csv,.py,.js" />
        </label>
      </div>

      {/* Stats */}
      {stats && (
        <div className="flex gap-4 text-sm text-text-secondary">
          <span>{stats.documents} documents</span>
          <span>{stats.chunks} chunks</span>
          <span>{((stats.total_size || 0) / 1024).toFixed(1)} KB total</span>
        </div>
      )}

      {/* Search */}
      <div className="flex gap-2">
        <input value={query} onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="Search knowledge base..."
          className="flex-1 bg-bg-card border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary" />
        <button onClick={handleSearch} className="bg-primary text-white px-4 py-2 rounded-lg text-sm">
          <Search className="w-4 h-4" />
        </button>
      </div>

      {/* Search results */}
      {results && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-text-secondary">{results.length} results</h3>
          {results.map((r, i) => (
            <div key={i} className="bg-bg-card border border-border rounded-lg p-3">
              <div className="flex justify-between text-xs text-text-secondary mb-1">
                <span>{r.doc_filename}</span>
                <span>Score: {r.score}</span>
              </div>
              <p className="text-sm">{r.text?.slice(0, 300)}</p>
            </div>
          ))}
        </div>
      )}

      {/* Document list */}
      <div className="space-y-2">
        <h2 className="text-sm font-medium text-text-secondary">Documents</h2>
        {docs.map((doc) => (
          <div key={doc.id} className="bg-bg-card border border-border rounded-lg p-3 flex items-center gap-3">
            <FileText className="w-5 h-5 text-text-secondary shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{doc.filename}</div>
              <div className="text-xs text-text-secondary">
                {doc.num_chunks} chunks | {(doc.size / 1024).toFixed(1)} KB
              </div>
            </div>
            <button onClick={() => handleDelete(doc.id)} className="p-1.5 text-text-secondary hover:text-red-400">
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
        {docs.length === 0 && (
          <p className="text-text-secondary text-sm text-center py-8">No documents yet. Upload your first document above.</p>
        )}
      </div>
    </div>
  )
}
