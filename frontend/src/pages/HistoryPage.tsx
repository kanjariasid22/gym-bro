import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type WorkoutSession } from '../api'
import { AppNav } from '../components/AppNav'

export function HistoryPage() {
  const [sessions, setSessions] = useState<WorkoutSession[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void (async () => {
      try {
        setSessions(await api.listSessions())
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load history')
      }
    })()
  }, [])

  return (
    <div className="shell">
      <AppNav />
      <main className="history">
        <h1>Workout history</h1>
        {error && <p className="error">{error}</p>}
        {sessions.length === 0 && !error && <p className="muted">No sessions yet.</p>}
        <ul className="history-list">
          {sessions.map((s) => (
            <li key={s.id}>
              <Link to={`/history/${s.id}`}>
                <span>Session #{s.id}</span>
                <span className={`status ${s.status}`}>{s.status}</span>
                <span className="muted">{new Date(s.started_at).toLocaleString()}</span>
              </Link>
            </li>
          ))}
        </ul>
      </main>
    </div>
  )
}
