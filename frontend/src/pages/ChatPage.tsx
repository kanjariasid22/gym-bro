import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, type SetLog, type WorkoutSession } from '../api'
import { useAuth } from '../AuthContext'

export function ChatPage() {
  const { user, logout } = useAuth()
  const [session, setSession] = useState<WorkoutSession | null>(null)
  const [sets, setSets] = useState<SetLog[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Manual set logging form (until chat/NL in later slices)
  const [rawName, setRawName] = useState('')
  const [weight, setWeight] = useState('')
  const [reps, setReps] = useState('')
  const [notes, setNotes] = useState('')

  const mode = session?.status === 'active' ? 'trainer' : 'guide'

  const refresh = useCallback(async () => {
    try {
      const active = await api.getActiveSession()
      setSession(active)
      if (active) {
        const detail = await api.getSession(active.id)
        setSets(detail.set_logs)
      } else {
        setSets([])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load session')
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  async function startWorkout() {
    setBusy(true)
    setError(null)
    try {
      const s = await api.startSession()
      setSession(s)
      setSets([])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Start failed')
    } finally {
      setBusy(false)
    }
  }

  async function endWorkout() {
    if (!session) return
    setBusy(true)
    setError(null)
    try {
      await api.completeSession(session.id)
      setSession(null)
      setSets([])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'End failed')
    } finally {
      setBusy(false)
    }
  }

  async function cancelWorkout() {
    if (!session) return
    setBusy(true)
    setError(null)
    try {
      await api.cancelSession(session.id)
      setSession(null)
      setSets([])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cancel failed')
    } finally {
      setBusy(false)
    }
  }

  async function addSet(e: FormEvent) {
    e.preventDefault()
    if (!session) return
    setBusy(true)
    setError(null)
    try {
      const row = await api.createSet(session.id, {
        raw_name: rawName,
        weight: Number(weight),
        unit: user?.unit_preference ?? 'kg',
        reps: Number(reps),
        notes: notes || undefined,
      })
      setSets((prev) => [...prev, row])
      setRawName('')
      setWeight('')
      setReps('')
      setNotes('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Log set failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">GymBro</div>
        <div className={`mode-chip ${mode}`}>
          {mode === 'trainer' ? 'Trainer · live' : 'Guide'}
        </div>
        <nav>
          <Link to="/history">History</Link>
          <button type="button" className="linkish" onClick={() => void logout()}>
            Log out
          </button>
        </nav>
      </header>

      <div className="session-controls">
        {session?.status === 'active' ? (
          <>
            <button type="button" disabled={busy} onClick={() => void endWorkout()}>
              End workout
            </button>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => void cancelWorkout()}
            >
              Cancel session
            </button>
          </>
        ) : (
          <button type="button" disabled={busy} onClick={() => void startWorkout()}>
            Start workout
          </button>
        )}
      </div>

      {error && <p className="error banner">{error}</p>}

      <div className="main-grid">
        <section className="chat-panel">
          <div className="chat-placeholder">
            <p>Chat arrives in later slices (persistence → LLM → Guide/Trainer).</p>
            <p className="muted">Mode follows hard session state above.</p>
          </div>
        </section>

        <aside className="session-strip">
          <h2>Session strip</h2>
          {session?.status === 'active' ? (
            <>
              <p className="muted">Session #{session.id}</p>
              <ul className="set-list">
                {sets.length === 0 && <li className="muted">No sets yet</li>}
                {sets.map((s) => (
                  <li key={s.id}>
                    <strong>{s.canonical_name}</strong> · set {s.set_index}: {s.weight}
                    {s.unit} × {s.reps}
                    {s.notes ? ` — ${s.notes}` : ''}
                  </li>
                ))}
              </ul>
              <form className="set-form" onSubmit={addSet}>
                <h3>Log a set</h3>
                <input
                  placeholder="Exercise (e.g. lat pd)"
                  value={rawName}
                  onChange={(e) => setRawName(e.target.value)}
                  required
                />
                <div className="row">
                  <input
                    type="number"
                    step="any"
                    placeholder="Weight"
                    value={weight}
                    onChange={(e) => setWeight(e.target.value)}
                    required
                  />
                  <input
                    type="number"
                    placeholder="Reps"
                    value={reps}
                    onChange={(e) => setReps(e.target.value)}
                    required
                  />
                </div>
                <input
                  placeholder="Notes (optional)"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
                <button type="submit" disabled={busy}>
                  Add set
                </button>
              </form>
            </>
          ) : (
            <p className="muted">Start a workout to see live sets here.</p>
          )}
        </aside>
      </div>
    </div>
  )
}
