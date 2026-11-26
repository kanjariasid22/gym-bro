import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type ProgramSummary } from '../api'
import { AppNav } from '../components/AppNav'

export function PlanHistoryPage() {
  const [programs, setPrograms] = useState<ProgramSummary[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void (async () => {
      try {
        setPrograms(await api.listPrograms())
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load plan history')
      }
    })()
  }, [])

  return (
    <div className="shell">
      <AppNav />
      <main className="history">
        <div className="plan-header">
          <h1>Plan history</h1>
          <Link to="/plan">Current plan</Link>
        </div>
        {error && <p className="error">{error}</p>}
        {programs.length === 0 && !error && <p className="muted">No plans yet.</p>}
        <ul className="history-list">
          {programs.map((p) => (
            <li key={p.id}>
              <Link to={`/plan/${p.id}`}>
                <span>
                  Plan #{p.id}
                  {p.goals ? ` — ${p.goals.slice(0, 60)}${p.goals.length > 60 ? '…' : ''}` : ''}
                </span>
                <span className={`status ${p.status}`}>{p.status}</span>
                <span className="muted">{new Date(p.created_at).toLocaleString()}</span>
              </Link>
            </li>
          ))}
        </ul>
      </main>
    </div>
  )
}
