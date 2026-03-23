import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { api } from '../api/client'
import { Settings, User, Cpu, CheckCircle, XCircle, Loader2, Eye, EyeOff } from 'lucide-react'

const PROVIDERS = [
  {
    value: 'qwen-cloud',
    label: '阿里云 Qwen (DashScope)',
    placeholder: 'sk-xxxxxxxxxxxxxxxx',
    url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: ['qwen-plus', 'qwen-turbo', 'qwen-max', 'qwen-long'],
  },
  {
    value: 'openai',
    label: 'OpenAI',
    placeholder: 'sk-xxxxxxxxxxxxxxxx',
    url: 'https://api.openai.com/v1',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
  },
  {
    value: 'vllm',
    label: '本地 vLLM / OpenAI-Compatible',
    placeholder: '(可选)',
    url: 'http://192.168.1.23:8001',
    models: ['qwen3.5-35b-a3b', 'qwen3.5-9b'],
  },
  {
    value: 'custom',
    label: '自定义端点',
    placeholder: '(可选)',
    url: '',
    models: [],
  },
]

export default function SettingsPage() {
  const { user } = useAuth()
  const [llm, setLlm] = useState({ provider: '', api_key: '', base_url: '', model: '', providers: [] })
  const [form, setForm] = useState({ provider: '', api_key: '', base_url: '', model: '' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [showKey, setShowKey] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')

  useEffect(() => {
    api.get('/settings/llm').then(d => {
      setLlm(d)
      setForm({ provider: d.provider || '', api_key: '', base_url: d.base_url || '', model: d.model || '' })
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const selectedProvider = PROVIDERS.find(p => p.value === form.provider)

  const handleProviderChange = (v) => {
    const p = PROVIDERS.find(x => x.value === v)
    setForm(f => ({ ...f, provider: v, base_url: p?.url || '', model: p?.models?.[0] || '' }))
    setTestResult(null)
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveMsg('')
    try {
      const payload = { ...form }
      if (!payload.api_key) delete payload.api_key
      const res = await api.post('/settings/llm', payload)
      setLlm(res)
      setForm(f => ({ ...f, api_key: '' }))
      setSaveMsg('保存成功')
      setTimeout(() => setSaveMsg(''), 3000)
    } catch (e) {
      setSaveMsg('保存失败：' + (e.message || '未知错误'))
    }
    setSaving(false)
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await api.post('/settings/llm/test', {})
      setTestResult(res)
    } catch (e) {
      setTestResult({ ok: false, error: e.message })
    }
    setTesting(false)
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-xl font-bold flex items-center gap-2">
        <Settings className="w-6 h-6 text-text-secondary" /> 设置
      </h1>

      {/* 用户信息 */}
      <div className="bg-bg-card border border-border rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold flex items-center gap-2">
          <User className="w-4 h-4" /> 用户信息
        </h2>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-text-secondary block mb-1">用户名</label>
            <div className="bg-bg border border-border rounded-lg px-3 py-2 text-sm">{user?.username}</div>
          </div>
          <div>
            <label className="text-xs text-text-secondary block mb-1">邮箱</label>
            <div className="bg-bg border border-border rounded-lg px-3 py-2 text-sm">{user?.email}</div>
          </div>
        </div>
      </div>

      {/* AI 模型配置 */}
      <div className="bg-bg-card border border-border rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold flex items-center gap-2">
          <Cpu className="w-4 h-4 text-primary" /> AI 模型配置
        </h2>

        <div className="flex items-center gap-2 text-xs">
          {llm.providers?.length > 0 ? (
            <>
              <CheckCircle className="w-3.5 h-3.5 text-accent" />
              <span className="text-accent">已配置：{llm.providers.join(', ')}</span>
            </>
          ) : (
            <>
              <XCircle className="w-3.5 h-3.5 text-red-400" />
              <span className="text-red-400">未配置 LLM，AI Chat 无法使用</span>
            </>
          )}
        </div>

        {loading ? (
          <div className="text-text-secondary text-sm">加载中...</div>
        ) : (
          <div className="space-y-3">
            <div>
              <label className="text-xs text-text-secondary block mb-1">服务商</label>
              <select
                value={form.provider}
                onChange={e => handleProviderChange(e.target.value)}
                className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
              >
                <option value="">-- 选择服务商 --</option>
                {PROVIDERS.map(p => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>

            {form.provider && form.provider !== 'vllm' && (
              <div>
                <label className="text-xs text-text-secondary block mb-1">
                  API Key
                  {llm.api_key && <span className="text-accent ml-1">（已保存：{llm.api_key}）</span>}
                </label>
                <div className="relative">
                  <input
                    type={showKey ? 'text' : 'password'}
                    value={form.api_key}
                    onChange={e => setForm(f => ({ ...f, api_key: e.target.value }))}
                    placeholder={llm.api_key ? '留空保持不变' : (selectedProvider?.placeholder || '输入 API Key')}
                    className="w-full bg-bg border border-border rounded-lg px-3 py-2 pr-10 text-sm focus:outline-none focus:border-primary"
                  />
                  <button
                    onClick={() => setShowKey(v => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text"
                  >
                    {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            )}

            {(form.provider === 'vllm' || form.provider === 'custom') && (
              <div>
                <label className="text-xs text-text-secondary block mb-1">API 地址 (Base URL)</label>
                <input
                  type="text"
                  value={form.base_url}
                  onChange={e => setForm(f => ({ ...f, base_url: e.target.value }))}
                  placeholder="http://192.168.1.23:8001"
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
                />
              </div>
            )}

            {form.provider && (
              <div>
                <label className="text-xs text-text-secondary block mb-1">模型</label>
                {selectedProvider?.models?.length > 0 ? (
                  <select
                    value={form.model}
                    onChange={e => setForm(f => ({ ...f, model: e.target.value }))}
                    className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
                  >
                    {selectedProvider.models.map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                    <option value="">自定义...</option>
                  </select>
                ) : (
                  <input
                    type="text"
                    value={form.model}
                    onChange={e => setForm(f => ({ ...f, model: e.target.value }))}
                    placeholder="模型名称"
                    className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
                  />
                )}
              </div>
            )}

            <div className="flex gap-2 pt-1">
              <button
                onClick={handleSave}
                disabled={saving || !form.provider}
                className="bg-primary hover:bg-primary-dark text-white text-sm px-4 py-2 rounded-lg transition-colors disabled:opacity-40 flex items-center gap-2"
              >
                {saving && <Loader2 className="w-4 h-4 animate-spin" />}
                保存配置
              </button>
              <button
                onClick={handleTest}
                disabled={testing}
                className="bg-bg border border-border hover:bg-bg-secondary text-sm px-4 py-2 rounded-lg transition-colors disabled:opacity-40 flex items-center gap-2"
              >
                {testing && <Loader2 className="w-4 h-4 animate-spin" />}
                测试连接
              </button>
            </div>

            {saveMsg && (
              <p className={`text-xs ${saveMsg.includes('成功') ? 'text-accent' : 'text-red-400'}`}>
                {saveMsg}
              </p>
            )}

            {testResult && (
              <div className={`text-xs p-3 rounded-lg border ${
                testResult.ok
                  ? 'border-accent/30 bg-accent/5 text-accent'
                  : 'border-red-400/30 bg-red-400/5 text-red-400'
              }`}>
                {testResult.ok
                  ? `连接成功 (${testResult.provider}) — 响应: "${testResult.response}"`
                  : `连接失败: ${testResult.error}`}
              </div>
            )}

            <div className="text-xs text-text-secondary space-y-1 pt-2 border-t border-border">
              <p>• 阿里云 Qwen：登录 DashScope 控制台获取 API Key（有免费额度）</p>
              <p>• 本地 vLLM：确保 Spark1 的 8001 端口可从此服务器访问</p>
              <p>• 配置保存后立即生效，无需重启</p>
            </div>
          </div>
        )}
      </div>

      {/* 系统信息 */}
      <div className="bg-bg-card border border-border rounded-xl p-5 space-y-2">
        <h2 className="text-sm font-semibold">系统信息</h2>
        <div className="text-xs text-text-secondary space-y-1">
          <p>版本：AI Workflow Terminal v0.8 Cloud Edition</p>
          <p>后端：FastAPI + SQLAlchemy + Qdrant</p>
          <p>认证：JWT Bearer Token</p>
        </div>
      </div>
    </div>
  )
}
