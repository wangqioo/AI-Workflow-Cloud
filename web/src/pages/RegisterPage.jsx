import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Cpu } from 'lucide-react'

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', email: '', password: '', confirm: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (form.password !== form.confirm) {
      setError('Passwords do not match')
      return
    }
    setLoading(true)
    const result = await register(form.username, form.email, form.password)
    setLoading(false)
    if (result.ok) navigate('/')
    else setError(result.error)
  }

  const update = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <Cpu className="w-12 h-12 text-primary mx-auto mb-3" />
          <h1 className="text-2xl font-bold">AI Workflow Terminal</h1>
          <p className="text-text-secondary text-sm mt-1">Create your account</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-bg-card border border-border rounded-xl p-6 space-y-4">
          <h2 className="text-lg font-semibold text-center">Register</h2>

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm text-text-secondary mb-1">Username</label>
            <input type="text" value={form.username} onChange={update('username')}
              className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
              required autoFocus />
          </div>

          <div>
            <label className="block text-sm text-text-secondary mb-1">Email</label>
            <input type="email" value={form.email} onChange={update('email')}
              className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
              required />
          </div>

          <div>
            <label className="block text-sm text-text-secondary mb-1">Password</label>
            <input type="password" value={form.password} onChange={update('password')}
              className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
              required minLength={6} />
          </div>

          <div>
            <label className="block text-sm text-text-secondary mb-1">Confirm Password</label>
            <input type="password" value={form.confirm} onChange={update('confirm')}
              className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
              required minLength={6} />
          </div>

          <button type="submit" disabled={loading}
            className="w-full bg-primary hover:bg-primary-dark text-white font-medium py-2 rounded-lg transition-colors disabled:opacity-50">
            {loading ? 'Creating account...' : 'Create Account'}
          </button>

          <p className="text-center text-sm text-text-secondary">
            Already have an account?{' '}
            <Link to="/login" className="text-primary hover:underline">Sign in</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
