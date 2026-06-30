import { useState } from 'react'
import { authLogin, authRegister, saveAuth } from '../api'

export default function Login({ onLogin }) {
  const [mode, setMode]         = useState('login') // 'login' | 'register'
  const [name, setName]         = useState('')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = mode === 'login'
        ? await authLogin(email, password)
        : await authRegister(email, password, name)
      saveAuth(data.access_token, data.user)
      onLogin(data.user)
    } catch (err) {
      setError(err.message)
    }
    setLoading(false)
  }

  function toggle() {
    setMode(m => m === 'login' ? 'register' : 'login')
    setError('')
    setName('')
    setEmail('')
    setPassword('')
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg)',
    }}>
      <div style={{
        width: '100%',
        maxWidth: 380,
        padding: '0 1rem',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{
            width: 44, height: 44,
            background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
            borderRadius: 12,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '1rem', fontWeight: 800, color: '#fff',
            margin: '0 auto 0.85rem',
            boxShadow: '0 4px 20px rgba(99,102,241,0.4)',
            letterSpacing: '-0.03em',
          }}>OP</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text)', letterSpacing: '-0.02em' }}>
            OpsPilot
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text3)', marginTop: 4 }}>
            {mode === 'login' ? 'Sign in to your workspace' : 'Create your account'}
          </div>
        </div>

        {/* Card */}
        <div style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          padding: '1.75rem',
        }}>
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {mode === 'register' && (
              <div>
                <label style={labelStyle}>Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="Your name"
                  required
                  style={inputStyle}
                />
              </div>
            )}

            <div>
              <label style={labelStyle}>Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                autoComplete="email"
                style={inputStyle}
              />
            </div>

            <div>
              <label style={labelStyle}>Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder={mode === 'register' ? 'Min. 6 characters' : '••••••••'}
                required
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                style={inputStyle}
              />
            </div>

            {error && (
              <div style={{
                background: 'var(--red-dim)',
                border: '1px solid rgba(239,68,68,0.3)',
                borderRadius: 6,
                padding: '0.55rem 0.75rem',
                fontSize: '0.82rem',
                color: 'var(--red)',
              }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{
                marginTop: '0.25rem',
                width: '100%',
                padding: '0.7rem',
                background: loading ? 'var(--accent-muted)' : 'var(--accent)',
                color: '#fff',
                border: 'none',
                borderRadius: 8,
                fontFamily: 'Inter, sans-serif',
                fontSize: '0.88rem',
                fontWeight: 600,
                cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'background 0.15s',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
              }}
            >
              {loading && <div style={{
                width: 14, height: 14, borderRadius: '50%',
                border: '2px solid rgba(255,255,255,0.3)',
                borderTopColor: '#fff',
                animation: 'spin 0.7s linear infinite',
              }} />}
              {loading ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>

          <div style={{
            marginTop: '1.25rem',
            paddingTop: '1.25rem',
            borderTop: '1px solid var(--border)',
            textAlign: 'center',
            fontSize: '0.8rem',
            color: 'var(--text3)',
          }}>
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <button
              onClick={toggle}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--accent)', fontFamily: 'Inter, sans-serif',
                fontSize: '0.8rem', fontWeight: 600, padding: 0,
              }}
            >
              {mode === 'login' ? 'Sign up' : 'Sign in'}
            </button>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        input:focus { outline: none; border-color: var(--accent) !important; box-shadow: 0 0 0 2px rgba(99,102,241,0.15); }
      `}</style>
    </div>
  )
}

const labelStyle = {
  display: 'block',
  fontSize: '0.78rem',
  fontWeight: 500,
  color: 'var(--text2)',
  marginBottom: '0.35rem',
}

const inputStyle = {
  width: '100%',
  background: 'var(--surface2)',
  border: '1px solid var(--border2)',
  borderRadius: 7,
  color: 'var(--text)',
  fontFamily: 'Inter, sans-serif',
  fontSize: '0.88rem',
  padding: '0.6rem 0.85rem',
  transition: 'border-color 0.15s',
  boxSizing: 'border-box',
}
