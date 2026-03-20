import { useAuth } from '../context/AuthContext'
import { Settings, User, Shield, Bell } from 'lucide-react'

export default function SettingsPage() {
  const { user } = useAuth()

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-xl font-bold flex items-center gap-2">
        <Settings className="w-6 h-6 text-text-secondary" /> Settings
      </h1>

      <div className="bg-bg-card border border-border rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold flex items-center gap-2">
          <User className="w-4 h-4" /> Profile
        </h2>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-text-secondary block mb-1">Username</label>
            <div className="bg-bg border border-border rounded-lg px-3 py-2 text-sm">{user?.username}</div>
          </div>
          <div>
            <label className="text-xs text-text-secondary block mb-1">Email</label>
            <div className="bg-bg border border-border rounded-lg px-3 py-2 text-sm">{user?.email}</div>
          </div>
        </div>
      </div>

      <div className="bg-bg-card border border-border rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold flex items-center gap-2">
          <Shield className="w-4 h-4" /> API Info
        </h2>
        <div className="text-sm text-text-secondary space-y-1">
          <p>Backend: AI Workflow Terminal v0.8</p>
          <p>API: FastAPI + SQLAlchemy + Qdrant</p>
          <p>Auth: JWT Bearer Token</p>
        </div>
      </div>
    </div>
  )
}
