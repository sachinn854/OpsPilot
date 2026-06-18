import { useState } from 'react'
import { createRun } from '../api'

export default function NewRun({ onDone }) {
  const [goal, setGoal] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    if (!goal.trim()) return
    setLoading(true)
    setError('')
    try {
      const result = await createRun(goal.trim())
      onDone(result.run_id)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1>New Run</h1>
      <form onSubmit={handleSubmit} style={{ maxWidth: 600 }}>
        <div className="field">
          <label>Goal</label>
          <textarea
            rows={4}
            placeholder="e.g. Check production API latency and summarise any open GitHub issues…"
            value={goal}
            onChange={e => setGoal(e.target.value)}
          />
        </div>
        {error && <p className="error">{error}</p>}
        <button type="submit" className="btn btn-primary" disabled={loading || !goal.trim()}>
          {loading ? 'Running…' : 'Start Run'}
        </button>
      </form>
    </div>
  )
}
