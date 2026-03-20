import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { Upload, File, Trash2, Download } from 'lucide-react'

export default function FilesPage() {
  const [files, setFiles] = useState([])
  const [stats, setStats] = useState(null)
  const [uploading, setUploading] = useState(false)

  const load = () => {
    api.get('/files').then(d => setFiles(d.files || []))
    api.get('/files/stats').then(setStats)
  }
  useEffect(load, [])

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    const fd = new FormData()
    fd.append('file', file)
    await api.upload('/files/upload', fd)
    setUploading(false)
    load()
    e.target.value = ''
  }

  const handleDelete = async (id) => {
    await api.delete(`/files/${id}`)
    load()
  }

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <Upload className="w-6 h-6 text-primary" /> File Manager
        </h1>
        <label className="bg-primary hover:bg-primary-dark text-white text-sm px-4 py-2 rounded-lg cursor-pointer flex items-center gap-2">
          <Upload className="w-4 h-4" />
          {uploading ? 'Uploading...' : 'Upload File'}
          <input type="file" className="hidden" onChange={handleUpload} />
        </label>
      </div>

      {stats && (
        <div className="text-sm text-text-secondary">
          {stats.total_files} files | {stats.total_size_mb} MB total
        </div>
      )}

      <div className="space-y-2">
        {files.map(f => (
          <div key={f.file_id} className="bg-bg-card border border-border rounded-lg p-3 flex items-center gap-3">
            <File className="w-5 h-5 text-text-secondary shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{f.filename}</div>
              <div className="text-xs text-text-secondary">{formatSize(f.size)} | {f.mime_type}</div>
            </div>
            <a href={`/api/files/${f.file_id}`} className="p-1.5 text-text-secondary hover:text-primary">
              <Download className="w-4 h-4" />
            </a>
            <button onClick={() => handleDelete(f.file_id)} className="p-1.5 text-text-secondary hover:text-red-400">
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
        {files.length === 0 && (
          <p className="text-text-secondary text-sm text-center py-8">No files uploaded yet.</p>
        )}
      </div>
    </div>
  )
}
