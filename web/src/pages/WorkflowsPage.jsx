import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { GitBranch, Plus, Play, Clock, Trash2 } from 'lucide-react'

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState([])
  const [stats, setStats] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', description: '' })

  const load = () => {
    api.get('/workflow/list').then(d => setWorkflows(d.workflows || []))
    api.get('/workflow/stats').then(setStats)
  }
  useEffect(load, [])

  const handleCreate = async (e) => {
    e.preventDefault()
    await api.post('/workflow/create', {
      name: form.name,
      description: form.description,
      definition: { workflow: { steps: [] } },
    })
    setShowCreate(false)
    setForm({ name: '', description: '' })
    load()
  }

  const handleDelete = async (id) => {
    await api.delete(`/workflow/${id}`)
    load()
  }

  const handleExecute = async (id) => {
    const result = await api.post(`/workflow/${id}/execute`, { input_data: {} })
    alert(`Execution: ${result.status || 'started'}`)
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <GitBranch className="w-6 h-6 text-purple-400" /> Workflows
        </h1>
        <button onClick={() => setShowCreate(!showCreate)}
          className="bg-primary hover:bg-primary-dark text-white text-sm px-4 py-2 rounded-lg flex items-center gap-2">
          <Plus className="w-4 h-4" /> New Workflow
        </button>
      </div>

      {stats && (
        <div className="flex gap-4 text-sm text-text-secondary">
          <span>{stats.total_workflows} workflows</span>
          <span>{stats.total_executions} executions</span>
        </div>
      )}

      {showCreate && (
        <form onSubmit={handleCreate} className="bg-bg-card border border-border rounded-xl p-4 space-y-3">
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Workflow name" required
            className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary" />
          <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="Description (optional)"
            className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary" />
          <div className="flex gap-2">
            <button type="submit" className="bg-primary text-white text-sm px-4 py-2 rounded-lg">Create</button>
            <button type="button" onClick={() => setShowCreate(false)} className="text-sm text-text-secondary px-4 py-2">Cancel</button>
          </div>
        </form>
      )}

      <div className="space-y-2">
        {workflows.map((wf) => (
          <div key={wf.id} className="bg-bg-card border border-border rounded-lg p-4 flex items-center gap-3">
            <GitBranch className="w-5 h-5 text-purple-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="font-medium text-sm">{wf.name}</div>
              <div className="text-xs text-text-secondary">{wf.description || 'No description'}</div>
            </div>
            <div className="flex gap-1">
              <button onClick={() => handleExecute(wf.id)}
                className="p-2 text-text-secondary hover:text-accent rounded hover:bg-white/5" title="Execute">
                <Play className="w-4 h-4" />
              </button>
              <button onClick={() => handleDelete(wf.id)}
                className="p-2 text-text-secondary hover:text-red-400 rounded hover:bg-white/5" title="Delete">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
        {workflows.length === 0 && (
          <p className="text-text-secondary text-sm text-center py-8">No workflows yet. Create your first workflow above.</p>
        )}
      </div>
    </div>
  )
}
