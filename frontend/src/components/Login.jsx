import { useState } from 'react'
import { authLogin, authRegister, saveAuth } from '../api'

export default function Login({ onLogin }) {
  const [mode, setMode]         = useState('login')
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
      background: 'var(--bg)',
      overflow: 'hidden',
    }}>
      {/* Left panel — brand */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        padding: '4rem 5rem',
        background: 'var(--sidebar)',
        borderRight: '1px solid var(--border)',
        minWidth: 0,
      }}>
        <div style={{ maxWidth: 420 }}>
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.9rem', marginBottom: '2.5rem' }}>
            <div style={{
              width: 44, height: 44,
              background: 'linear-gradient(135deg, #818cf8 0%, #6366f1 100%)',
              borderRadius: 12,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '0.75rem', fontWeight: 700, color: '#fff',
              boxShadow: '0 0 0 1px rgba(129,140,248,0.3), 0 4px 20px rgba(129,140,248,0.4)',
              letterSpacing: '0.04em', flexShrink: 0,
            }}>OP</div>
            <div>
              <div style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '1.1rem', fontWeight: 600, color: 'var(--text)', letterSpacing: '-0.01em',
              }}>OpsPilot</div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text3)', letterSpacing: '0.01em' }}>AI Operations Copilot</div>
            </div>
          </div>

          {/* Headline */}
          <h1 style={{
            fontSize: '2rem',
            fontWeight: 700,
            color: 'var(--text)',
            letterSpacing: '-0.04em',
            lineHeight: 1.2,
            marginBottom: '1rem',
          }}>
            Your AI ops team,<br />
            <span style={{ color: 'var(--accent)' }}>always on duty.</span>
          </h1>
          <p style={{ fontSize: '0.88rem', color: 'var(--text2)', lineHeight: 1.7, maxWidth: 340 }}>
            Give it a goal. It plans, researches, executes, and verifies — pausing for your approval before anything sensitive.
          </p>

          {/* Feature dots */}
          <div style={{ marginTop: '2.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {[
              { icon: '▶', text: 'Multi-agent runs with self-reflection' },
              { icon: '◈', text: 'Human-in-the-loop for sensitive actions' },
              { icon: '⊙', text: '20+ tools — GitHub, Slack, RAG, SQL' },
            ].map((f, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{
                  width: 28, height: 28,
                  borderRadius: 7,
                  background: 'var(--accent-dim)',
                  border: '1px solid rgba(129,140,248,0.2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '0.7rem', color: 'var(--accent)', flexShrink: 0,
                }}>{f.icon}</div>
                <span style={{ fontSize: '0.84rem', color: 'var(--text2)' }}>{f.text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel — form */}
      <div style={{
        width: 440,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem 3rem',
        flexShrink: 0,
      }}>
        <div style={{ width: '100%', maxWidth: 360 }}>
          <div style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--text)', letterSpacing: '-0.025em', marginBottom: '0.3rem' }}>
              {mode === 'login' ? 'Sign in' : 'Create account'}
            </h2>
            <p style={{ fontSize: '0.82rem', color: 'var(--text2)' }}>
              {mode === 'login' ? 'Welcome back to your workspace' : 'Get started with OpsPilot'}
            </p>
          </div>

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
                border: '1px solid rgba(251,76,106,0.3)',
                borderRadius: 8,
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
                marginTop: '0.35rem',
                width: '100%',
                padding: '0.75rem',
                background: loading ? 'var(--accent-muted)' : 'var(--accent)',
                color: '#fff',
                border: 'none',
                borderRadius: 10,
                fontFamily: 'Inter, sans-serif',
                fontSize: '0.9rem',
                fontWeight: 600,
                cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'background 0.15s, box-shadow 0.15s',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                boxShadow: loading ? 'none' : '0 2px 12px rgba(129,140,248,0.35)',
              }}
            >
              {loading && (
                <div style={{
                  width: 15, height: 15, borderRadius: '50%',
                  border: '2px solid rgba(255,255,255,0.25)',
                  borderTopColor: '#fff',
                  animation: 'spin 0.7s linear infinite',
                }} />
              )}
              {loading ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>

          <div style={{
            marginTop: '1.5rem',
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
        input:focus {
          outline: none;
          border-color: var(--accent) !important;
          box-shadow: 0 0 0 3px rgba(129,140,248,0.12) !important;
        }
        @media (max-width: 700px) {
          .login-left { display: none; }
        }
      `}</style>
    </div>
  )
}

const labelStyle = {
  display: 'block',
  fontFamily: "'JetBrains Mono', monospace",
  fontSize: '0.67rem',
  fontWeight: 600,
  color: 'var(--text3)',
  textTransform: 'uppercase',
  letterSpacing: '0.1em',
  marginBottom: '0.4rem',
}

const inputStyle = {
  width: '100%',
  background: 'var(--surface)',
  border: '1px solid var(--border2)',
  borderRadius: 9,
  color: 'var(--text)',
  fontFamily: 'Inter, sans-serif',
  fontSize: '0.88rem',
  padding: '0.65rem 0.9rem',
  transition: 'border-color 0.15s, box-shadow 0.15s',
  boxSizing: 'border-box',
}
