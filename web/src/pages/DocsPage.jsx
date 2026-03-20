import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { FileText, Upload, Clock } from 'lucide-react'

export default function DocsPage() {
  const [docs, setDocs] = useState([])
  const [projects, setProjects] = useState([])
  const [uploading, setUploading] = useState(false)

  const load = () => {
    api.get('/docs/list').then(d => setDocs(d.documents || []))
    api.get('/docs/projects').then(d => setProjects(d.projects || []))
  }
  useEffect(load, [])

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    const text = await file.text()
    await api.post('/docs/ingest', {
      content: text,
      title: file.name.replace(/\.[^.]+$/, ''),
      source_file: file.name,
    })
    setUploading(false)
    load()
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <FileText className="w-6 h-6 text-blue-400" /> Document Manager
        </h1>
        <label className="bg-primary hover:bg-primary-dark text-white text-sm px-4 py-2 rounded-lg cursor-pointer flex items-center gap-2">
          <Upload className="w-4 h-4" />
          {uploading ? 'Uploading...' : 'Upload'}
          <input type="file" className="hidden" onChange={handleUpload} accept=".txt,.md,.json,.csv" />
        </label>
      </div>

      {projects.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {projects.map(p => (
            <span key={p.name} className="bg-bg-card border border-border rounded-full px-3 py-1 text-xs text-text-secondary">
              {p.name} ({p.doc_count})
            </span>
          ))}
        </div>
      )}

      <div className="space-y-2">
        {docs.map((doc) => (
          <div key={doc.doc_id} className="bg-bg-card border border-border rounded-lg p-3 flex items-center gap-3">
            <FileText className="w-5 h-5 text-text-secondary shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium">{doc.title}</div>
              <div className="text-xs text-text-secondary flex gap-2">
                <span>v{doc.version_count}</span>
                {doc.project && <span>{doc.project}</span>}
                {doc.doc_type && <span>{doc.doc_type}</span>}
              </div>
            </div>
            <div className="text-xs text-text-secondary flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {doc.updated_at ? new Date(doc.updated_at).toLocaleDateString() : '-'}
            </div>
          </div>
        ))}
        {docs.length === 0 && (
          <p className="text-text-secondary text-sm text-center py-8">No documents yet.</p>
        )}
      </div>
    </div>
  )
}
