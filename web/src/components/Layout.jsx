import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  Home, MessageSquare, Database, GitBranch, FileText,
  ListTodo, Mail, Languages, Volume2, Globe, Activity,
  Upload, Settings, LogOut, Menu, X, Cpu,
} from 'lucide-react'

const NAV_ITEMS = [
  { to: '/', icon: Home, label: 'Dashboard' },
  { to: '/chat', icon: MessageSquare, label: 'AI Chat' },
  { to: '/knowledge', icon: Database, label: 'Knowledge Base' },
  { to: '/workflows', icon: GitBranch, label: 'Workflows' },
  { to: '/docs', icon: FileText, label: 'Documents' },
  { to: '/tasks', icon: ListTodo, label: 'Tasks' },
  { to: '/email', icon: Mail, label: 'Email' },
  { to: '/translate', icon: Languages, label: 'Translator' },
  { to: '/files', icon: Upload, label: 'Files' },
  { to: '/system', icon: Activity, label: 'System' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed lg:static inset-y-0 left-0 z-30
        w-60 bg-bg-secondary border-r border-border
        flex flex-col
        transform transition-transform duration-200
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        {/* Logo */}
        <div className="p-4 border-b border-border flex items-center gap-2">
          <Cpu className="w-6 h-6 text-primary" />
          <span className="font-semibold text-lg">AI Workflow</span>
          <span className="text-xs text-text-secondary ml-auto">v0.8</span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-2">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) => `
                flex items-center gap-3 px-4 py-2.5 mx-2 rounded-lg text-sm
                transition-colors duration-150
                ${isActive
                  ? 'bg-primary/15 text-primary font-medium'
                  : 'text-text-secondary hover:bg-white/5 hover:text-text'}
              `}
              end={to === '/'}
            >
              <Icon className="w-4.5 h-4.5 shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User footer */}
        <div className="p-3 border-t border-border">
          <div className="flex items-center gap-2 px-2">
            <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary text-sm font-medium">
              {user?.username?.[0]?.toUpperCase() || '?'}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{user?.username}</div>
              <div className="text-xs text-text-secondary truncate">{user?.email}</div>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 rounded hover:bg-white/10 text-text-secondary hover:text-red-400"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar (mobile) */}
        <div className="lg:hidden flex items-center gap-3 p-3 border-b border-border bg-bg-secondary">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 rounded hover:bg-white/10"
          >
            <Menu className="w-5 h-5" />
          </button>
          <span className="font-medium">AI Workflow Terminal</span>
        </div>

        <div className="flex-1 overflow-y-auto p-4 lg:p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
