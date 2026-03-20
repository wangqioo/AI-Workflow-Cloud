import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { Activity, Cpu, HardDrive, Thermometer, Clock } from 'lucide-react'

function Gauge({ label, value, icon: Icon }) {
  const pct = Math.min(100, value || 0)
  const color = pct > 80 ? '#ef4444' : pct > 60 ? '#eab308' : '#10b981'
  return (
    <div className="bg-bg-card border border-border rounded-xl p-4 text-center">
      <Icon className="w-6 h-6 mx-auto mb-2 text-text-secondary" />
      <div className="text-2xl font-bold" style={{ color }}>{pct.toFixed(1)}%</div>
      <div className="text-xs text-text-secondary mt-1">{label}</div>
    </div>
  )
}

export default function SystemPage() {
  const [data, setData] = useState(null)
  const [engines, setEngines] = useState(null)

  useEffect(() => {
    api.get('/system/status').then(setData)
    api.get('/engines/health').then(setEngines)
  }, [])

  const formatUptime = (s) => {
    const d = Math.floor(s / 86400)
    const h = Math.floor((s % 86400) / 3600)
    const m = Math.floor((s % 3600) / 60)
    return `${d}d ${h}h ${m}m`
  }

  if (!data) return <div className="text-center py-20 text-text-secondary">Loading...</div>

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-xl font-bold flex items-center gap-2">
        <Activity className="w-6 h-6 text-accent" /> System Monitor
      </h1>

      {/* Gauges */}
      <div className="grid grid-cols-3 gap-4">
        <Gauge label="CPU Usage" value={data.cpu?.usage_pct} icon={Cpu} />
        <Gauge label="Memory" value={data.memory?.percent} icon={HardDrive} />
        <Gauge label="Disk" value={data.disk?.percent} icon={HardDrive} />
      </div>

      {/* Details */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-bg-card border border-border rounded-xl p-4 space-y-2">
          <h3 className="text-sm font-semibold mb-2">Memory</h3>
          <div className="text-xs text-text-secondary flex justify-between">
            <span>Used</span><span>{data.memory?.used_mb} MB</span>
          </div>
          <div className="text-xs text-text-secondary flex justify-between">
            <span>Total</span><span>{data.memory?.total_mb} MB</span>
          </div>
          <div className="text-xs text-text-secondary flex justify-between">
            <span>Available</span><span>{data.memory?.available_mb} MB</span>
          </div>
        </div>
        <div className="bg-bg-card border border-border rounded-xl p-4 space-y-2">
          <h3 className="text-sm font-semibold mb-2">System</h3>
          <div className="text-xs text-text-secondary flex justify-between">
            <span>Uptime</span><span>{formatUptime(data.uptime_seconds)}</span>
          </div>
          <div className="text-xs text-text-secondary flex justify-between">
            <span>Platform</span><span>{data.platform?.system} {data.platform?.machine}</span>
          </div>
          <div className="text-xs text-text-secondary flex justify-between">
            <span>Load (1m)</span><span>{data.load?.['1min']}</span>
          </div>
        </div>
      </div>

      {/* Engine health */}
      {engines?.services && (
        <div className="bg-bg-card border border-border rounded-xl p-4">
          <h3 className="text-sm font-semibold mb-3">Engine Health</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {Object.entries(engines.services).map(([name, info]) => (
              <div key={name} className="flex items-center gap-2 text-xs">
                <span className={`w-2 h-2 rounded-full ${info.healthy ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-text-secondary">{name}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
