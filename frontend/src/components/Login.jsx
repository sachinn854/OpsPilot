import { useEffect, useState } from 'react'
import { authLogin, authRegister, saveAuth } from '../api'

export default function Login({ onLogin }) {
  const [mode, setMode]         = useState('login')
  const [name, setName]         = useState('')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw]     = useState(false)
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [step, setStep]         = useState(0)

  // cycle pipeline demo
  useEffect(() => {
    const t = setInterval(() => setStep(s => (s + 1) % 4), 1800)
    return () => clearInterval(t)
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      const data = mode==='login'
        ? await authLogin(email, password)
        : await authRegister(email, password, name)
      saveAuth(data.access_token, data.user)
      onLogin(data.user)
    } catch (err) { setError(err.message) }
    setLoading(false)
  }
  function toggle(){
    setMode(m=>m==='login'?'register':'login')
    setError(''); setName(''); setEmail(''); setPassword('')
  }

  const PIPELINE = [
    { k:'Plan',     d:'Decompose goal into steps',  c:'#7c7cff' },
    { k:'Research', d:'RAG + tools gather context', c:'#06b6d4' },
    { k:'Execute',  d:'Call tools via MCP registry',c:'#f59e0b' },
    { k:'Verify',   d:'Critic checks & retries',    c:'#10b981' },
  ]

  return (
    <div className="login-root">
      {/* ── LEFT — brand + showcase ── */}
      <div className="login-left">
        {/* mesh + orbs background */}
        <div className="login-mesh" aria-hidden />
        <div className="orb orb-1" aria-hidden />
        <div className="orb orb-2" aria-hidden />
        <div className="orb orb-3" aria-hidden />
        <div className="login-grid" aria-hidden />

        <div className="login-left-inner">
          {/* top bar */}
          <div className="login-brand">
            <div className="login-logo">OP</div>
            <div>
              <div className="login-wordmark">OpsPilot</div>
              <div className="login-sub">AI Operations Copilot</div>
            </div>
            <span className="login-badge">● SOC 2 Ready</span>
          </div>

          {/* hero */}
          <div className="login-hero">
            <div className="login-eyebrow">
              <span className="login-dot" /> Trusted by ops teams · 20+ MCP tools
            </div>
            <h1 className="login-h1">
              Your AI ops team,<br />
              <span className="login-grad">always on duty.</span>
            </h1>
            <p className="login-lead">
              Give it a goal. It <em>plans</em>, <em>researches</em>, <em>executes</em> &amp; <em>verifies</em> —
              pausing for your approval before anything sensitive.
            </p>
          </div>

          {/* animated pipeline */}
          <div className="login-pipeline" aria-label="Pipeline demo">
            <div className="login-pipe-track">
              <div className="login-pipe-line" />
              <div className="login-pipe-progress" style={{ width: `${((step+1)/4)*100}%` }} />
              <div className="login-pipe-dot" style={{ left: `calc(${((step)/3)*100}% - 6px)` }} />
            </div>
            <div className="login-pipe-steps">
              {PIPELINE.map((p,i)=>(
                <div key={p.k} className={`login-pipe-step ${i===step?'active':''} ${i<step?'done':''}`}>
                  <div className="login-pipe-icon" style={{ borderColor: p.c, color: p.c, background: i===step? `${p.c}18` : i<step? `${p.c}12` : 'rgba(255,255,255,0.04)' }}>
                    {i<step ? '✓' : ['◈','◎','▶','◆'][i]}
                  </div>
                  <div className="login-pipe-k">{p.k}</div>
                  <div className="login-pipe-d">{p.d}</div>
                </div>
              ))}
            </div>
          </div>

          {/* feature cards */}
          <div className="login-features">
            {[
              { t:'Multi-agent with self-reflection', d:'Planner → Research → Execution → Critic loop', icon:'▶' },
              { t:'Human-in-the-loop',               d:'Sensitive tools pause for Approve / Reject',   icon:'◈' },
              { t:'MCP tool registry',                d:'GitHub, Slack, Notion, Jira, Linear & more',  icon:'⊙' },
            ].map(f=>(
              <div key={f.t} className="login-feat">
                <div className="login-feat-icon">{f.icon}</div>
                <div>
                  <div className="login-feat-t">{f.t}</div>
                  <div className="login-feat-d">{f.d}</div>
                </div>
              </div>
            ))}
          </div>

          {/* stats + logos */}
          <div className="login-stats">
            <div className="login-stat"><b>99.9%</b><span>Uptime runs</span></div>
            <div className="login-stat"><b>20+</b><span>Tools</span></div>
            <div className="login-stat"><b>&lt;2s</b><span>Avg tool call</span></div>
            <div className="login-stat"><b>HITL</b><span>Safe by default</span></div>
          </div>
          <div className="login-logos" aria-label="Trusted">
            <span>GitHub</span><i>·</i><span>Slack</span><i>·</i><span>Linear</span><i>·</i><span>Notion</span><i>·</i><span>Jira</span><i>·</i><span>PagerDuty</span>
          </div>
        </div>
      </div>

      {/* ── RIGHT — auth card ── */}
      <div className="login-right">
        <div className="login-card">
          <div className="login-card-head">
            <h2>{mode==='login' ? 'Welcome back' : 'Create account'}</h2>
            <p>{mode==='login' ? 'Sign in to your workspace' : 'Get started in 30 seconds — no credit card'}</p>
          </div>

          <form onSubmit={handleSubmit} className="login-form">
            {mode==='register' && (
              <label className="login-field">
                <span>Name</span>
                <input type="text" value={name} onChange={e=>setName(e.target.value)} placeholder="Ada Lovelace" required />
              </label>
            )}
            <label className="login-field">
              <span>Email</span>
              <input type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@company.com" required autoComplete="email" />
            </label>
            <label className="login-field">
              <span>Password</span>
              <div className="login-pw-wrap">
                <input
                  type={showPw?'text':'password'}
                  value={password} onChange={e=>setPassword(e.target.value)}
                  placeholder={mode==='register'?'Min. 6 characters':'••••••••'}
                  required autoComplete={mode==='login'?'current-password':'new-password'}
                />
                <button type="button" className="login-eye" onClick={()=>setShowPw(v=>!v)} aria-label={showPw?'Hide':'Show'}>
                  {showPw?'Hide':'Show'}
                </button>
              </div>
            </label>

            {error && <div className="login-error">{error}</div>}

            <button type="submit" disabled={loading} className={`login-submit ${loading?'loading':''}`}>
              {loading && <span className="login-spinner" />}
              {loading ? 'Please wait…' : mode==='login' ? 'Sign In →' : 'Create Account →'}
            </button>
          </form>

          <div className="login-switch">
            {mode==='login' ? "Don't have an account? " : 'Already have an account? '}
            <button onClick={toggle}> {mode==='login' ? 'Sign up' : 'Sign in'}</button>
          </div>

          <div className="login-foot">
            <span>🔒</span> Encrypted at rest · Tokens never leave your org · <a href="#" onClick={e=>e.preventDefault()}>Privacy</a>
          </div>
        </div>

        {/* bottom hint card */}
        <div className="login-hint">
          <div className="login-hint-icon">✦</div>
          <div>
            <b>Try a demo goal after sign-in</b>
            <span>“Summarise open PRs and notify Slack” — watch the full pipeline live.</span>
          </div>
        </div>
      </div>

      {/* ── styles ── */}
      <style>{`
        .login-root{
          height:100vh; min-height:100vh; max-height:100vh; display:flex; overflow:hidden;
          background:#07070a; color:var(--text);
        }

        /* LEFT — occupies most of screen, side gutters minimized to use empty space */
        .login-left{
          flex:1.9; position:relative; overflow-y:auto; overflow-x:hidden;
          display:flex;
          border-right:1px solid rgba(255,255,255,0.06);
          isolation:isolate; min-height:0; height:100vh; max-height:100vh;
          scrollbar-width:none; -ms-overflow-style:none;
        }
        .login-left::-webkit-scrollbar{ display:none; width:0; height:0; }
        .login-mesh{
          position:absolute; inset:0;
          background:
            radial-gradient(800px 600px at 18% 10%, rgba(124,60,255,0.22), transparent 60%),
            radial-gradient(700px 500px at 88% 18%, rgba(6,182,214,0.16), transparent 60%),
            radial-gradient(900px 600px at 55% 92%, rgba(16,185,129,0.10), transparent 62%),
            radial-gradient(600px 400px at 30% 75%, rgba(245,158,11,0.08), transparent 60%),
            linear-gradient(180deg, #0b0b12 0%, #07070a 55%, #0a0f14 100%);
        }
        .orb{
          position:absolute; border-radius:50%; filter:blur(28px); opacity:0.55; pointer-events:none;
          animation: float 9s ease-in-out infinite;
        }
        .orb-1{ width:520px; height:520px; left:-140px; top:-160px; background:radial-gradient(circle at 30% 30%, rgba(124,60,255,0.45), transparent 68%); animation-delay:0s; }
        .orb-2{ width:480px; height:480px; right:-120px; top:6%; background:radial-gradient(circle at 30% 30%, rgba(6,182,214,0.32), transparent 70%); animation-delay:-2.5s; }
        .orb-3{ width:620px; height:620px; left:22%; bottom:-220px; background:radial-gradient(circle at 30% 30%, rgba(16,185,129,0.18), transparent 72%); animation-delay:-5s; }
        .login-grid{
          position:absolute; inset:0; opacity:0.06;
          background-image:
            linear-gradient(rgba(255,255,255,0.9) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.9) 1px, transparent 1px);
          background-size:32px 32px;
          mask-image: radial-gradient(900px 600px at 40% 20%, black 55%, transparent 85%);
        }
        .login-left-inner{
          position:relative; z-index:1;
          width:100%; max-width:800px; margin:0 auto;
          padding:1.8rem 3rem 1.6rem;
          display:flex; flex-direction:column; gap:1.05rem;
          animation: rise 0.7s ease both;
        }
        .login-brand{ display:flex; align-items:center; gap:0.75rem; }
        .login-logo{
          width:40px; height:40px; border-radius:11px; display:grid; place-items:center;
          background: linear-gradient(135deg, #7c3aed 0%, #6366f1 40%, #06b6d4 100%);
          color:#fff; font-family:'JetBrains Mono', monospace; font-weight:800; font-size:0.70rem; letter-spacing:0.04em;
          box-shadow: 0 1px 0 rgba(255,255,255,0.16) inset, 0 8px 24px rgba(124,60,255,0.35), 0 0 0 1px rgba(255,255,255,0.08);
        }
        .login-wordmark{ font-family:'JetBrains Mono', monospace; font-weight:800; font-size:0.95rem; letter-spacing:-0.02em; color:#fff; }
        .login-sub{ font-size:0.66rem; letter-spacing:0.10em; text-transform:uppercase; font-weight:700; color:rgba(255,255,255,0.55); margin-top:1px; }
        .login-badge{
          margin-left:auto; font-family:'JetBrains Mono', monospace; font-size:0.62rem; font-weight:700;
          letter-spacing:0.08em; text-transform:uppercase; color:#a7f3d0;
          background: rgba(16,185,129,0.12); border:1px solid rgba(16,185,129,0.22);
          padding:0.22rem 0.5rem; border-radius:999px;
        }

        .login-hero{ margin-top:0.3rem; }
        .login-eyebrow{
          display:inline-flex; align-items:center; gap:0.45rem;
          font-family:'JetBrains Mono', monospace; font-size:0.68rem; font-weight:700; letter-spacing:0.08em; text-transform:uppercase;
          color:rgba(255,255,255,0.62);
          background: rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.08);
          padding:0.28rem 0.6rem; border-radius:999px; backdrop-filter: blur(8px);
        }
        .login-dot{ width:6px; height:6px; border-radius:50%; background:#10b981; box-shadow:0 0 10px rgba(16,185,129,0.7); }
        .login-h1{
          margin:0.85rem 0 0.6rem; font-size:2.85rem; font-weight:900; line-height:1.03; letter-spacing:-0.05em; color:#fff;
        }
        .login-grad{
          background: linear-gradient(90deg, #a78bfa 0%, #7c7cff 28%, #22d3ee 62%, #34d399 100%);
          -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
          filter: drop-shadow(0 1px 18px rgba(124,60,255,0.25));
        }
        .login-lead{
          font-size:1rem; line-height:1.6; color:rgba(255,255,255,0.78); max-width:none;
        }
        .login-lead em{ font-style:normal; color:#fff; font-weight:600; border-bottom:1px solid rgba(255,255,255,0.14); padding-bottom:1px; }

        /* pipeline */
        .login-pipeline{
          margin-top:0.2rem; background: rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.07);
          border-radius:14px; padding:0.9rem 0.9rem 0.75rem; backdrop-filter: blur(10px);
          box-shadow: 0 8px 32px rgba(0,0,0,0.32);
        }
        .login-pipe-track{
          position:relative; height:4px; background: rgba(255,255,255,0.08); border-radius:999px; overflow:hidden; margin:2px 6px 0.75rem;
        }
        .login-pipe-line{ position:absolute; inset:0; background: linear-gradient(90deg, rgba(124,124,255,0.12), rgba(6,182,214,0.12), rgba(16,185,129,0.12)); }
        .login-pipe-progress{
          position:absolute; left:0; top:0; bottom:0; border-radius:999px;
          background: linear-gradient(90deg, #7c7cff, #06b6d4, #10b981);
          box-shadow: 0 0 14px rgba(124,124,255,0.35);
          transition: width 0.6s ease;
        }
        .login-pipe-dot{
          position:absolute; top:50%; width:12px; height:12px; margin-top:-6px; border-radius:50%;
          background:#fff; border:2px solid #7c7cff; box-shadow: 0 0 0 4px rgba(124,124,255,0.18), 0 2px 10px rgba(0,0,0,0.35);
          transition: left 0.6s cubic-bezier(0.34,1.2,0.64,1);
        }
        .login-pipe-steps{ display:grid; grid-template-columns: repeat(4, 1fr); gap:0.45rem; }
        .login-pipe-step{ text-align:center; padding:0.45rem 0.3rem 0.35rem; border-radius:10px; border:1px solid transparent; transition: all 0.35s; }
        .login-pipe-step.active{ background: rgba(124,124,255,0.08); border-color: rgba(124,124,255,0.16); transform: translateY(-1px); }
        .login-pipe-step.done{ opacity:0.9; }
        .login-pipe-icon{
          width:30px; height:30px; border-radius:9px; margin:0 auto 0.4rem; display:grid; place-items:center;
          font-size:0.72rem; font-weight:800; border:1px solid;
          transition: all 0.35s;
        }
        .login-pipe-k{ font-family:'JetBrains Mono', monospace; font-size:0.66rem; font-weight:800; letter-spacing:0.08em; text-transform:uppercase; color:rgba(255,255,255,0.9); }
        .login-pipe-d{ font-size:0.68rem; color:rgba(255,255,255,0.55); line-height:1.35; margin-top:2px; }

        .login-features{ display:flex; flex-direction:column; gap:0.45rem; }
        .login-feat{
          display:flex; gap:0.7rem; align-items:center;
          background: rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06);
          border-radius:12px; padding:0.6rem 0.7rem; backdrop-filter: blur(8px);
          transition: transform 0.15s, border-color 0.15s;
        }
        .login-feat:hover{ transform: translateY(-1px); border-color: rgba(124,124,255,0.16); }
        .login-feat-icon{
          width:28px; height:28px; border-radius:8px; display:grid; place-items:center; flex-shrink:0;
          background: rgba(124,124,255,0.12); border:1px solid rgba(124,124,255,0.18); color:#b4b8ff; font-size:0.72rem;
        }
        .login-feat-t{ font-size:0.82rem; font-weight:700; color:#fff; letter-spacing:-0.01em; }
        .login-feat-d{ font-size:0.72rem; color:rgba(255,255,255,0.62); }

        .login-stats{ display:grid; grid-template-columns: repeat(4, 1fr); gap:0.45rem; }
        .login-stat{
          background: rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06);
          border-radius:10px; padding:0.55rem 0.6rem; text-align:center;
        }
        .login-stat b{ display:block; font-size:0.95rem; font-weight:850; color:#fff; letter-spacing:-0.02em; }
        .login-stat span{ font-size:0.66rem; color:rgba(255,255,255,0.55); font-family:'JetBrains Mono', monospace; letter-spacing:0.04em; }
        .login-logos{
          display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap;
          font-family:'JetBrains Mono', monospace; font-size:0.66rem; font-weight:700;
          letter-spacing:0.08em; text-transform:uppercase; color:rgba(255,255,255,0.38);
          border-top:1px solid rgba(255,255,255,0.06); padding-top:0.75rem; margin-top:0.05rem;
        }
        .login-logos i{ font-style:normal; opacity:0.35; }

        .login-right{
          width:560px; flex-shrink:0; display:flex; flex-direction:column; align-items:center; justify-content:center;
          padding:2rem 2.6rem; gap:0.9rem; overflow:hidden; height:100vh; max-height:100vh;
          background:
            radial-gradient(600px 400px at 60% 12%, rgba(124,60,255,0.08), transparent 60%),
            linear-gradient(180deg, #0f0f14 0%, #0b0b0f 100%);
          position:relative;
        }
        .login-card{
          width:100%; max-width:380px;
          background: rgba(255,255,255,0.04);
          border:1px solid rgba(255,255,255,0.08);
          border-radius:16px; padding:1.35rem 1.35rem 1.15rem;
          box-shadow: 0 16px 48px rgba(0,0,0,0.45), 0 1px 0 rgba(255,255,255,0.06) inset;
          backdrop-filter: blur(16px) saturate(1.15);
          animation: rise 0.7s 0.08s ease both;
        }
        .login-card-head h2{ font-size:1.25rem; font-weight:850; color:#fff; letter-spacing:-0.03em; }
        .login-card-head p{ font-size:0.82rem; color:rgba(255,255,255,0.62); margin-top:0.2rem; }

        .login-form{ display:flex; flex-direction:column; gap:0.85rem; margin-top:1.05rem; }
        .login-field{ display:flex; flex-direction:column; gap:0.32rem; }
        .login-field span{
          font-family:'JetBrains Mono', monospace; font-size:0.62rem; font-weight:750;
          letter-spacing:0.10em; text-transform:uppercase; color:rgba(255,255,255,0.55);
        }
        .login-field input{
          width:100%; background: rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.10);
          border-radius:10px; color:#fff; font-family:'Inter', sans-serif; font-size:0.88rem;
          padding:0.66rem 0.9rem; transition: border-color 0.14s, box-shadow 0.14s, background 0.14s;
          box-sizing:border-box;
        }
        .login-field input::placeholder{ color:rgba(255,255,255,0.35); }
        .login-field input:focus{ outline:none; border-color: rgba(124,124,255,0.42); box-shadow: 0 0 0 3px rgba(124,124,255,0.16); background: rgba(255,255,255,0.08); }
        .login-pw-wrap{ position:relative; display:flex; align-items:center; }
        .login-pw-wrap input{ padding-right:3.2rem; }
        .login-eye{
          position:absolute; right:6px; top:6px; bottom:6px; padding:0 0.55rem;
          background: rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.08); border-radius:8px;
          color:rgba(255,255,255,0.7); font-family:'JetBrains Mono', monospace; font-size:0.66rem; font-weight:700;
          cursor:pointer; transition: all 0.12s;
        }
        .login-eye:hover{ background: rgba(255,255,255,0.10); color:#fff; }

        .login-error{
          background: rgba(239,68,68,0.10); border:1px solid rgba(239,68,68,0.22); color:#fecaca;
          border-radius:10px; padding:0.55rem 0.7rem; font-size:0.82rem;
        }
        .login-submit{
          margin-top:0.2rem; width:100%; padding:0.78rem; border-radius:10px;
          background: linear-gradient(90deg, #7c3aed 0%, #6366f1 45%, #4f46e5 100%);
          color:#fff; border:1px solid rgba(255,255,255,0.10); font-family:'Inter', sans-serif;
          font-size:0.92rem; font-weight:800; letter-spacing:-0.01em;
          cursor:pointer; display:flex; align-items:center; justify-content:center; gap:0.5rem;
          box-shadow: 0 8px 22px rgba(99,102,241,0.35), 0 1px 0 rgba(255,255,255,0.12) inset;
          transition: transform 0.12s, box-shadow 0.12s, filter 0.12s;
        }
        .login-submit:hover{ transform: translateY(-1px); box-shadow: 0 10px 28px rgba(99,102,241,0.42), 0 1px 0 rgba(255,255,255,0.12) inset; filter: brightness(1.05); }
        .login-submit:active{ transform:none; }
        .login-submit.loading{ opacity:0.85; cursor:wait; }
        .login-spinner{ width:15px; height:15px; border-radius:50%; border:2px solid rgba(255,255,255,0.28); border-top-color:#fff; animation: spin 0.7s linear infinite; display:inline-block; }

        .login-switch{
          margin-top:1rem; text-align:center; font-size:0.80rem; color:rgba(255,255,255,0.55);
        }
        .login-switch button{
          background:none; border:none; cursor:pointer; color:#a5b4fc; font-family:'Inter', sans-serif;
          font-size:0.80rem; font-weight:750; padding:0;
        }
        .login-switch button:hover{ color:#c4b5fd; text-decoration:underline; text-underline-offset:3px; }
        .login-foot{
          margin-top:0.9rem; padding-top:0.85rem; border-top:1px solid rgba(255,255,255,0.06);
          display:flex; align-items:center; justify-content:center; gap:0.35rem;
          font-size:0.68rem; color:rgba(255,255,255,0.42); text-align:center;
        }
        .login-foot a{ color:rgba(255,255,255,0.55); text-decoration:none; border-bottom:1px solid rgba(255,255,255,0.14); }
        .login-foot a:hover{ color:#fff; }

        .login-hint{
          width:100%; max-width:380px; display:flex; gap:0.7rem; align-items:flex-start;
          background: linear-gradient(90deg, rgba(124,124,255,0.10), rgba(6,182,214,0.08));
          border:1px solid rgba(124,124,255,0.16); border-radius:12px; padding:0.7rem 0.8rem;
          animation: rise 0.7s 0.16s ease both;
        }
        .login-hint-icon{
          width:26px; height:26px; border-radius:7px; display:grid; place-items:center; flex-shrink:0;
          background: rgba(124,124,255,0.16); border:1px solid rgba(124,124,255,0.18); color:#b4b8ff; font-size:0.72rem;
        }
        .login-hint b{ display:block; font-size:0.78rem; color:#fff; }
        .login-hint span{ font-size:0.72rem; color:rgba(255,255,255,0.62); line-height:1.45; }

        @keyframes float{ 0%,100%{ transform: translateY(0) } 50%{ transform: translateY(-10px) } }
        @keyframes rise{ from{ opacity:0; transform: translateY(10px) } to{ opacity:1; transform: translateY(0) } }
        @keyframes spin{ to{ transform: rotate(360deg) } }

        @media (max-width: 980px){
          .login-left{ display:none; }
          .login-right{ width:100%; }
        }
        @media (max-width: 520px){
          .login-card, .login-hint{ max-width: 100%; }
          .login-right{ padding:1.25rem; }
        }
      `}</style>
    </div>
  )
}
