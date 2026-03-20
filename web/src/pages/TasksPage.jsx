import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { ListTodo, Plus, ChevronRight } from 'lucide-react'

const STATUS_COLORS = {
  draft: 'bg-gray-500', sent: 'bg-blue-500', received: 'bg-indigo-500',
  accepted: 'bg-cyan-500', in_progress: 'bg-yellow-500', completed: 'bg-green-500',
  delivered: 'bg-emerald-500', closed: 'bg-gray-600', rejected: 'bg-red-500',
}

const PRIORITY_COLORS = {
  low: 'text-gray-400', medium: 'text-blue-400', high: 'text-orange-400', urgent: 'text-red-400',
}

export default function TasksPage() {
  const [tasks, setTasks] = useState([])
  const [stats, setStats] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ title: '', description: '', priority: 'medium' })
  const [selected, setSelected] = useState(null)

  const load = () => {
    api.get('/tasks').then(d => setTasks(d.tasks || []))
    api.get('/tasks/stats').then(setStats)
  }
  useEffect(load, [])

  const handleCreate = async (e) => {
    e.preventDefault()
    await api.post('/tasks', form)
    setShowCreate(false)
    setForm({ title: '', description: '', priority: 'medium' })
    load()
  }

  const handleTransition = async (taskId, target) => {
    await api.post(`/tasks/${taskId}/transition`, { target_status: target })
    load()
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <ListTodo className="w-6 h-6 text-yellow-400" /> Task Management
        </h1>
        <button onClick={() => setShowCreate(!showCreate)}
          className="bg-primary hover:bg-primary-dark text-white text-sm px-4 py-2 rounded-lg flex items-center gap-2">
          <Plus className="w-4 h-4" /> New Task
        </button>
      </div>

      {stats && (
        <div className="flex gap-4 text-sm text-text-secondary">
          <span>{stats.total} total</span>
          <span>{stats.completed || 0} completed</span>
          <span>{stats.completion_rate}% rate</span>
        </div>
      )}

      {showCreate && (
        <form onSubmit={handleCreate} className="bg-bg-card border border-border rounded-xl p-4 space-y-3">
          <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="Task title" required
            className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary" />
          <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="Description (optional)" rows={2}
            className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary resize-none" />
          <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}
            className="bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary">
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="urgent">Urgent</option>
          </select>
          <div className="flex gap-2">
            <button type="submit" className="bg-primary text-white text-sm px-4 py-2 rounded-lg">Create</button>
            <button type="button" onClick={() => setShowCreate(false)} className="text-sm text-text-secondary px-4 py-2">Cancel</button>
          </div>
        </form>
      )}

      <div className="space-y-2">
        {tasks.map((task) => (
          <div key={task.task_id} className="bg-bg-card border border-border rounded-lg p-3">
            <div className="flex items-center gap-3">
              <span className={`w-2 h-2 rounded-full ${STATUS_COLORS[task.status] || 'bg-gray-500'}`} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium">{task.title}</div>
                <div className="text-xs text-text-secondary flex gap-2">
                  <span className={PRIORITY_COLORS[task.priority]}>{task.priority}</span>
                  <span>{task.status}</span>
                  {task.progress?.percentage > 0 && <span>{task.progress.percentage}%</span>}
                </div>
              </div>
              <button onClick={() => setSelected(selected === task.task_id ? null : task.task_id)}
                className="p-1 text-text-secondary hover:text-text">
                <ChevronRight className={`w-4 h-4 transition-transform ${selected === task.task_id ? 'rotate-90' : ''}`} />
              </button>
            </div>
            {selected === task.task_id && (
              <div className="mt-3 pt-3 border-t border-border text-sm space-y-2">
                {task.description && <p className="text-text-secondary">{task.description}</p>}
                <div className="flex gap-2 flex-wrap">
                  {task.status === 'draft' && (
                    <button onClick={() => handleTransition(task.task_id, 'sent')}
                      className="bg-blue-500/20 text-blue-400 text-xs px-3 py-1 rounded">Send</button>
                  )}
                  {task.status === 'sent' && (
                    <button onClick={() => handleTransition(task.task_id, 'received')}
                      className="bg-indigo-500/20 text-indigo-400 text-xs px-3 py-1 rounded">Mark Received</button>
                  )}
                  {task.status === 'received' && (
                    <>
                      <button onClick={() => handleTransition(task.task_id, 'accepted')}
                        className="bg-cyan-500/20 text-cyan-400 text-xs px-3 py-1 rounded">Accept</button>
                      <button onClick={() => handleTransition(task.task_id, 'rejected')}
                        className="bg-red-500/20 text-red-400 text-xs px-3 py-1 rounded">Reject</button>
                    </>
                  )}
                  {task.status === 'accepted' && (
                    <button onClick={() => handleTransition(task.task_id, 'in_progress')}
                      className="bg-yellow-500/20 text-yellow-400 text-xs px-3 py-1 rounded">Start Work</button>
                  )}
                  {task.status === 'in_progress' && (
                    <button onClick={() => handleTransition(task.task_id, 'completed')}
                      className="bg-green-500/20 text-green-400 text-xs px-3 py-1 rounded">Complete</button>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
        {tasks.length === 0 && (
          <p className="text-text-secondary text-sm text-center py-8">No tasks yet. Create your first task above.</p>
        )}
      </div>
    </div>
  )
}
