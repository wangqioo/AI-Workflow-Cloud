import { createContext, useContext, useState, useEffect } from 'react'
import { api, setToken, clearToken } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (token) {
      api.get('/auth/me')
        .then(data => {
          if (data.username) setUser(data)
          else clearToken()
        })
        .catch(() => clearToken())
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = async (username, password) => {
    const data = await api.post('/auth/login', { username, password })
    if (data.access_token) {
      setToken(data.access_token)
      const me = await api.get('/auth/me')
      setUser(me)
      return { ok: true }
    }
    return { ok: false, error: data.detail || 'Login failed' }
  }

  const register = async (username, email, password) => {
    const data = await api.post('/auth/register', { username, email, password })
    if (data.username) {
      return login(username, password)
    }
    return { ok: false, error: data.detail || 'Registration failed' }
  }

  const logout = () => {
    clearToken()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
