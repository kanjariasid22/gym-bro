import { useEffect, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { api, type Program } from '../api'
import { AppNav } from '../components/AppNav'

export function PlanDetailPage() {
  const { id } = useParams()
  const programId = Number(id)
  const [program, setProgram] = useState<Program | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!Number.isFinite(programId)) return
    void (async () => {
      try {
        setProgram(await api.getProgramById(programId))
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load plan')
      }
    })()
  }, [programId])

  if (program?.status === 'active') {
    return <Navigate to="/plan" replace />
  }

  return (
    <div className="shell">
      <AppNav />
      <main className="history plan-page">
        <div className="plan-header">
          <h1>Plan #{programId}</h1>
          <Link to="/plan/history">← Plan history</Link>
        </div>
        {error && <p className="error">{error}</p>}
        {!program && !error && <p className="muted">Loading…</p>}
        {program && (
          <>
            <div className="plan-meta">
              <span className={`status ${program.status}`}>{program.status}</span>
              <p className="muted">Read-only archived plan</p>
              <p>
                <strong>Goals:</strong> {program.goals || '—'}
              </p>
              <p>
                <strong>End date:</strong> {program.end_date || '—'}
              </p>
              {program.notes && (
                <p>
                  <strong>Notes:</strong> {program.notes}
                </p>
              )}
              {program.archived_at && (
                <p className="muted">
                  Archived {new Date(program.archived_at).toLocaleString()}
                </p>
              )}
            </div>
            {program.days.map((d) => (
              <section key={d.id ?? d.day_index} className="plan-day-view">
                <h2>
                  Day {d.day_index}
                  {d.label ? ` · ${d.label}` : ''}
                </h2>
                <ul className="set-list">
                  {d.exercises.map((e) => (
                    <li key={e.id ?? `${e.canonical_name}-${e.order_index}`}>
                      <strong>{e.canonical_name}</strong>
                      {e.target_sets != null || e.target_reps
                        ? ` · ${e.target_sets ?? '?'}×${e.target_reps ?? '?'}`
                        : ''}
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </>
        )}
      </main>
    </div>
  )
}
