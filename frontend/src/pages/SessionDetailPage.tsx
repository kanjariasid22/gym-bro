import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type SessionDetail, type SetLog, type Unit } from '../api'

export function SessionDetailPage() {
  const { id } = useParams()
  const sessionId = Number(id)
  const [detail, setDetail] = useState<SessionDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<SetLog | null>(null)

  const load = useCallback(async () => {
    try {
      setDetail(await api.getSession(sessionId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load session')
    }
  }, [sessionId])

  useEffect(() => {
    void load()
  }, [load])

  async function removeSet(setId: number) {
    if (!confirm('Delete this set?')) return
    try {
      await api.deleteSet(setId)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  async function saveEdit(e: FormEvent) {
    e.preventDefault()
    if (!editing) return
    try {
      await api.patchSet(editing.id, {
        raw_name: editing.raw_name,
        weight: editing.weight,
        unit: editing.unit,
        reps: editing.reps,
        notes: editing.notes,
      })
      setEditing(null)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    }
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">GymBro</div>
        <nav>
          <Link to="/history">← History</Link>
        </nav>
      </header>
      <main className="history">
        <h1>Session #{sessionId}</h1>
        {detail && (
          <p className="muted">
            {detail.status} · started {new Date(detail.started_at).toLocaleString()}
          </p>
        )}
        {error && <p className="error">{error}</p>}

        <table className="sets-table">
          <thead>
            <tr>
              <th>Exercise</th>
              <th>Set</th>
              <th>Weight</th>
              <th>Unit</th>
              <th>Reps</th>
              <th>Notes</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {detail?.set_logs.map((s) => (
              <tr key={s.id}>
                <td>{s.canonical_name}</td>
                <td>{s.set_index}</td>
                <td>{s.weight}</td>
                <td>{s.unit}</td>
                <td>{s.reps}</td>
                <td>{s.notes ?? ''}</td>
                <td className="actions">
                  <button type="button" className="linkish" onClick={() => setEditing(s)}>
                    Edit
                  </button>
                  <button type="button" className="linkish" onClick={() => void removeSet(s.id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {detail && detail.set_logs.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">
                  No sets logged
                </td>
              </tr>
            )}
          </tbody>
        </table>

        {editing && (
          <form className="edit-form" onSubmit={saveEdit}>
            <h2>Edit set #{editing.id}</h2>
            <label>
              Exercise
              <input
                value={editing.raw_name}
                onChange={(e) => setEditing({ ...editing, raw_name: e.target.value })}
              />
            </label>
            <div className="row">
              <label>
                Weight
                <input
                  type="number"
                  step="any"
                  value={editing.weight}
                  onChange={(e) =>
                    setEditing({ ...editing, weight: Number(e.target.value) })
                  }
                />
              </label>
              <label>
                Unit
                <select
                  value={editing.unit}
                  onChange={(e) =>
                    setEditing({ ...editing, unit: e.target.value as Unit })
                  }
                >
                  <option value="kg">kg</option>
                  <option value="lbs">lbs</option>
                </select>
              </label>
              <label>
                Reps
                <input
                  type="number"
                  value={editing.reps}
                  onChange={(e) => setEditing({ ...editing, reps: Number(e.target.value) })}
                />
              </label>
            </div>
            <label>
              Notes
              <input
                value={editing.notes ?? ''}
                onChange={(e) => setEditing({ ...editing, notes: e.target.value })}
              />
            </label>
            <div className="row">
              <button type="submit">Save</button>
              <button type="button" className="secondary" onClick={() => setEditing(null)}>
                Cancel
              </button>
            </div>
          </form>
        )}
      </main>
    </div>
  )
}
