import { useEffect, useState } from 'react'

const STEPS = [
  {
    target: null,
    title: 'Welcome to OpsPilot! 👋',
    body: 'Your AI-powered enterprise copilot — connected to GitHub, Slack, Google, Jira, Notion, PagerDuty and more. Let me show you around in 60 seconds.',
    position: 'center',
  },
  {
    target: 'tour-chat',
    title: '💬 Chat',
    body: 'Talk directly to your AI assistant. Best for quick questions, simple lookups, and single-tool actions.\n\nExamples:\n• "Show my open GitHub issues"\n• "Send email to John"\n• "Who is on-call right now?"',
    position: 'right',
  },
  {
    target: 'tour-runs',
    title: '▶ Runs — Multi-Agent Goals',
    body: 'For complex, multi-step goals. The copilot plans → researches → calls tools → verifies → reports.\n\nExamples:\n• "Find root cause of prod outage, create a Jira ticket, and notify Slack"\n• "Find stale PRs and DM the owners"',
    position: 'right',
  },
  {
    target: 'tour-approvals',
    title: '◈ Approvals — Human in the Loop',
    body: 'Sensitive actions pause here and wait for your decision before executing.\n\nApprove or Reject — the AI waits. Covers production rollbacks, mass emails, file deletions, and any tool marked sensitive.',
    position: 'right',
  },
  {
    target: 'tour-documents',
    title: '⊡ Documents — Knowledge Base',
    body: 'Upload your company PDFs, runbooks, and docs. The AI searches them with RAG and returns cited, grounded answers.\n\nExamples:\n• HR policy PDFs\n• Architecture docs\n• Onboarding guides',
    position: 'right',
  },
  {
    target: 'tour-tools',
    title: '⊙ Tool Registry',
    body: 'Browse all connected tools in one place — GitHub, Slack, Google Workspace, Jira, Linear, Notion, Confluence, PagerDuty, HubSpot and more.\n\nSee each tool\'s description, parameters, and sensitivity status.',
    position: 'right',
  },
  {
    target: 'tour-slack',
    title: '# Slack — Bidirectional Bot',
    body: 'Set up the Slack bot and command the copilot directly from Slack. Configure keyword alerts and event triggers.\n\nHITL approvals can also be sent to Slack as interactive approve/reject buttons.',
    position: 'right',
  },
  {
    target: 'tour-settings',
    title: '⚙ Settings — Connect Everything',
    body: 'Connect all your services here:\n• Google (Gmail, Calendar, Drive, Sheets)\n• GitHub, Slack, Jira, Linear\n• Notion, Confluence, PagerDuty, HubSpot\n\nSave tokens and verify them live.',
    position: 'right',
  },
  {
    target: null,
    title: "You're all set! 🚀",
    body: 'OpsPilot is ready to use.\n\n→ Start with Chat for quick questions\n→ Go to Settings to connect your services\n→ Use Runs for complex multi-step goals\n\nGood luck!',
    position: 'center',
    isLast: true,
  },
]

export default function Tour({ onComplete }) {
  const [step, setStep] = useState(0)
  const [rect, setRect]   = useState(null)

  const current = STEPS[step]
  const total   = STEPS.length

  useEffect(() => {
    if (!current.target) { setRect(null); return }
    const el = document.getElementById(current.target)
    if (!el) { setRect(null); return }
    el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })

    let tid
    const update = () => {
      clearTimeout(tid)
      tid = setTimeout(() => setRect(el.getBoundingClientRect()), 80)
    }
    update()
    window.addEventListener('resize', update)
    return () => {
      clearTimeout(tid)
      window.removeEventListener('resize', update)
    }
  }, [step, current.target])

  function next() {
    if (step === total - 1) done()
    else setStep(s => s + 1)
  }
  function prev() { setStep(s => Math.max(0, s - 1)) }
  function done() {
    localStorage.setItem('opspilot_tour_done', '1')
    onComplete()
  }

  const PAD   = 6
  const isCenter = current.position === 'center' || !rect

  // tooltip card width
  const CARD_W = 320

  // card position: right of spotlight or centered
  let cardStyle = {}
  if (!isCenter && rect) {
    const top = Math.min(
      Math.max(rect.top + rect.height / 2 - 120, 16),
      window.innerHeight - 280,
    )
    cardStyle = {
      position: 'fixed',
      top,
      left: rect.right + 20,
      width: CARD_W,
    }
  } else {
    cardStyle = {
      position: 'fixed',
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
      width: CARD_W,
    }
  }

  return (
    <>
      {/* Dark overlay with spotlight cutout */}
      {rect ? (
        <svg
          style={{ position: 'fixed', inset: 0, width: '100vw', height: '100vh', zIndex: 9000, pointerEvents: 'none' }}
        >
          <defs>
            <mask id="tour-mask">
              <rect width="100%" height="100%" fill="white" />
              <rect
                x={rect.left - PAD}
                y={rect.top - PAD}
                width={rect.width + PAD * 2}
                height={rect.height + PAD * 2}
                rx="8"
                fill="black"
              />
            </mask>
          </defs>
          <rect width="100%" height="100%" fill="rgba(0,0,0,0.72)" mask="url(#tour-mask)" />
          {/* Spotlight glow ring */}
          <rect
            x={rect.left - PAD}
            y={rect.top - PAD}
            width={rect.width + PAD * 2}
            height={rect.height + PAD * 2}
            rx="8"
            fill="none"
            stroke="var(--accent, #6366f1)"
            strokeWidth="2"
            opacity="0.9"
          />
        </svg>
      ) : (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.72)',
          zIndex: 9000, pointerEvents: 'none',
        }} />
      )}

      {/* Backdrop click to skip */}
      <div
        style={{ position: 'fixed', inset: 0, zIndex: 9001, cursor: 'default' }}
        onClick={done}
      />

      {/* Tooltip card */}
      <div
        style={{
          ...cardStyle,
          zIndex: 9002,
          background: 'var(--surface2, #1e1e2e)',
          border: '1px solid var(--border2, #3f3f5a)',
          borderRadius: 12,
          boxShadow: '0 8px 40px rgba(0,0,0,0.6)',
          padding: '1.4rem 1.5rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.75rem',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Step counter */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', gap: '4px' }}>
            {STEPS.map((_, i) => (
              <div key={i} style={{
                width: i === step ? 18 : 6,
                height: 6,
                borderRadius: 3,
                background: i === step ? 'var(--accent, #6366f1)' : 'var(--border2, #3f3f5a)',
                transition: 'all 0.2s',
              }} />
            ))}
          </div>
          <button
            onClick={done}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--text3)', fontSize: '1rem', lineHeight: 1, padding: '2px 4px',
            }}
          >×</button>
        </div>

        {/* Title */}
        <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text)', lineHeight: 1.3 }}>
          {current.title}
        </div>

        {/* Body — preserve newlines */}
        <div style={{ fontSize: '0.8rem', color: 'var(--text2)', lineHeight: 1.7, whiteSpace: 'pre-line' }}>
          {current.body}
        </div>

        {/* Buttons */}
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
          {step > 0 && (
            <button
              onClick={prev}
              style={{
                flex: 1, padding: '0.5rem', borderRadius: 7, cursor: 'pointer',
                background: 'var(--surface3)', border: '1px solid var(--border2)',
                color: 'var(--text2)', fontSize: '0.8rem', fontWeight: 500,
              }}
            >← Back</button>
          )}
          <button
            onClick={next}
            style={{
              flex: 2, padding: '0.5rem', borderRadius: 7, cursor: 'pointer',
              background: 'var(--accent, #6366f1)', border: 'none',
              color: '#fff', fontSize: '0.8rem', fontWeight: 600,
            }}
          >
            {current.isLast ? 'Get Started →' : step === 0 ? 'Start Tour →' : 'Next →'}
          </button>
        </div>

        {!current.isLast && (
          <button
            onClick={done}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--text3)', fontSize: '0.73rem', textAlign: 'center',
            }}
          >Skip tour</button>
        )}
      </div>
    </>
  )
}
