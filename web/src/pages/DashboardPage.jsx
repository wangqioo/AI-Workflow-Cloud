import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { api } from '../api/client'
import {
  MessageSquare, Database, GitBranch, ListTodo,
  Cpu, HardDrive, MemoryStick, Activity,
} from 'lucide-react'

function StatCard({ icon: Icon, label, value, color = 'text-primary', to }) {
  const inner = (
    <div className="bg-bg-card border border-border rounded-xl p-4 hover:border-primary/30 transition-colors">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg bg-white/5 ${color}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <div className="text-2xl font-bold">{value ?? '-'}</div>
          <div className="text-xs text-text-secondary">{label}</div>
        </div>
      </div>
    </div>
  )
  return to ? <Link to={to}>{inner}</Link> : inner
}

function SystemBar({ label, value, max, unit = '%' }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0
  const color = pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-yellow-500' : 'bg-accent'
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-text-secondary">{label}</span>
        <span>{typeof value === 'number' ? value.toFixed(1) : value}{unit}</span>
      </div>
      <div className="h-2 bg-white/5 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [stats, setStats] = useState({})
  const [system, setSystem] = useState(null)

  useEffect(() => {
    Promise.all([
      api.get('/memory/context').catch(() => ({})),
      api.get('/rag/stats').catch(() => ({})),
      api.get('/workflow/stats').catch(() => ({})),
      api.get('/tasks/stats').catch(() => ({})),
      api.get('/system/quick').catch(() => null),
    ]).then(([mem, rag, wf, task, sys]) => {
      setStats({ mem, rag, wf, task })
      setSystem(sys)
    })
  }, [])

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Welcome */}
      <div>
        <h1 className="text-2xl font-bold">
          Welcome back, {user?.display_name || user?.username}
        </h1>
        <p className="text-text-secondary text-sm mt-1">AI Workflow Terminal v0.8 Cloud Dashboard</p>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard icon={Database} label="RAG Documents" value={stats.rag?.documents} to="/knowledge" />
        <StatCard icon={GitBranch} label="Workflows" value={stats.wf?.total_workflows} color="text-purple-400" to="/workflows" />
        <StatCard icon={ListTodo} label="Active Tasks" value={stats.task?.total} color="text-yellow-400" to="/tasks" />
        <StatCard icon={MessageSquare} label="Memory Items" value={stats.mem?.length || 0} color="text-accent" to="/chat" />
      </div>

      {/* System status */}
      {system && (
        <div className="bg-bg-card border border-border rounded-xl p-5">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-accent" />
            System Status
          </h2>
          <div className="grid md:grid-cols-3 gap-4">
            <SystemBar label="CPU" value={system.cpu_percent} max={100} />
            <SystemBar label="Memory" value={system.memory_percent} max={100} />
            <SystemBar label="Disk" value={system.disk_percent} max={100} />
          </div>
        </div>
      )}

      {/* Quick actions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { to: '/chat', label: 'Start Chat', icon: MessageSquare, desc: 'Talk to AI assistant' },
          { to: '/knowledge', label: 'Upload Docs', icon: Database, desc: 'Add to knowledge base' },
          { to: '/workflows', label: 'Workflows', icon: GitBranch, desc: 'Manage automations' },
          { to: '/tasks', label: 'New Task', icon: ListTodo, desc: 'Create a task' },
        ].map(({ to, label, icon: Icon, desc }) => (
          <Link key={to} to={to}
            className="bg-bg-card border border-border rounded-xl p-4 hover:border-primary/30 transition-colors group">
            <Icon className="w-6 h-6 text-text-secondary group-hover:text-primary mb-2" />
            <div className="font-medium text-sm">{label}</div>
            <div className="text-xs text-text-secondary">{desc}</div>
          </Link>
        ))}
      </div>
    </div>
  )
}
