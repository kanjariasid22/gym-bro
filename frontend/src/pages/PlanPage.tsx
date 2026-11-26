import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, type Program, type ProgramPut } from '../api'
import { AppNav } from '../components/AppNav'

type DraftExercise = {
  raw_name: string
  target_sets: string
  target_reps: string
  notes: string
}

type DraftDay = {
  day_index: number
  label: string
  scheduled_date: string
  exercises: DraftExercise[]
}

function emptyExercise(): DraftExercise {
  return { raw_name: '', target_sets: '', target_reps: '', notes: '' }
}

function emptyDay(index: number): DraftDay {
  return {
    day_index: index,
    label: '',
    scheduled_date: '',
    exercises: [emptyExercise()],
  }
}

function programToDraft(p: Program): {
  goals: string
  end_date: string
  notes: string
  days: DraftDay[]
} {
  return {
    goals: p.goals ?? '',
    end_date: p.end_date ?? '',
    notes: p.notes ?? '',
    days:
      p.days.length > 0
        ? p.days.map((d) => ({
            day_index: d.day_index,
            label: d.label ?? '',
            scheduled_date: d.scheduled_date ?? '',
            exercises:
              d.exercises.length > 0
                ? d.exercises.map((e) => ({
                    raw_name: e.raw_name || e.canonical_name,
                    target_sets: e.target_sets != null ? String(e.target_sets) : '',
                    target_reps: e.target_reps ?? '',
                    notes: e.notes ?? '',
                  }))
                : [emptyExercise()],
          }))
        : [emptyDay(1)],
  }
}

export function PlanPage() {
  const [program, setProgram] = useState<Program | null>(null)
  const [editing, setEditing] = useState(false)
  const [goals, setGoals] = useState('')
  const [endDate, setEndDate] = useState('')
  const [notes, setNotes] = useState('')
  const [days, setDays] = useState<DraftDay[]>([emptyDay(1)])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [loaded, setLoaded] = useState(false)

  const load = useCallback(async () => {
    const p = await api.getProgram()
    setProgram(p)
    if (p) {
      const d = programToDraft(p)
      setGoals(d.goals)
      setEndDate(d.end_date)
      setNotes(d.notes)
      setDays(d.days)
    } else {
      setGoals('')
      setEndDate('')
      setNotes('')
      setDays([emptyDay(1)])
    }
    setLoaded(true)
  }, [])

  useEffect(() => {
    void load().catch((err) =>
      setError(err instanceof Error ? err.message : 'Failed to load plan'),
    )
  }, [load])

  function startCreate() {
    setEditing(true)
    setGoals('')
    setEndDate('')
    setNotes('')
    setDays([emptyDay(1)])
  }

  function startEdit() {
    if (program) {
      const d = programToDraft(program)
      setGoals(d.goals)
      setEndDate(d.end_date)
      setNotes(d.notes)
      setDays(d.days)
    }
    setEditing(true)
  }

  async function onSave(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const body: ProgramPut = {
      goals: goals.trim() || null,
      end_date: endDate || null,
      notes: notes.trim() || null,
      days: days.map((d, i) => ({
        day_index: d.day_index || i + 1,
        label: d.label.trim() || null,
        scheduled_date: d.scheduled_date || null,
        exercises: d.exercises
          .filter((ex) => ex.raw_name.trim())
          .map((ex, j) => ({
            raw_name: ex.raw_name.trim(),
            target_sets: ex.target_sets ? Number(ex.target_sets) : null,
            target_reps: ex.target_reps.trim() || null,
            notes: ex.notes.trim() || null,
            order_index: j,
          })),
      })),
    }
    try {
      const saved = await api.putProgram(body)
      setProgram(saved)
      setEditing(false)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="shell">
      <AppNav />
      <main className="history plan-page">
        <div className="plan-header">
          <h1>Plan</h1>
          <Link to="/plan/history">Plan history</Link>
        </div>
        {error && <p className="error">{error}</p>}

        {!loaded ? (
          <p className="muted">Loading…</p>
        ) : editing ? (
          <form className="plan-editor" onSubmit={onSave}>
            <p className="muted">
              Saving creates a <strong>new</strong> active plan and archives the previous one.
            </p>
            <label>
              Goals
              <textarea value={goals} onChange={(e) => setGoals(e.target.value)} rows={2} />
            </label>
            <label>
              End date
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </label>
            <label>
              Notes
              <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
            </label>

            {days.map((day, di) => (
              <fieldset key={di} className="plan-day">
                <legend>Day {day.day_index || di + 1}</legend>
                <div className="row">
                  <label>
                    Label
                    <input
                      value={day.label}
                      onChange={(e) => {
                        const next = [...days]
                        next[di] = { ...day, label: e.target.value }
                        setDays(next)
                      }}
                      placeholder="Push / Upper / …"
                    />
                  </label>
                  <label>
                    Date (optional)
                    <input
                      type="date"
                      value={day.scheduled_date}
                      onChange={(e) => {
                        const next = [...days]
                        next[di] = { ...day, scheduled_date: e.target.value }
                        setDays(next)
                      }}
                    />
                  </label>
                </div>
                {day.exercises.map((ex, ei) => (
                  <div className="row plan-ex" key={ei}>
                    <input
                      placeholder="Exercise"
                      value={ex.raw_name}
                      required={ei === 0}
                      onChange={(e) => {
                        const next = [...days]
                        const exercises = [...day.exercises]
                        exercises[ei] = { ...ex, raw_name: e.target.value }
                        next[di] = { ...day, exercises }
                        setDays(next)
                      }}
                    />
                    <input
                      placeholder="Sets"
                      value={ex.target_sets}
                      onChange={(e) => {
                        const next = [...days]
                        const exercises = [...day.exercises]
                        exercises[ei] = { ...ex, target_sets: e.target.value }
                        next[di] = { ...day, exercises }
                        setDays(next)
                      }}
                    />
                    <input
                      placeholder="Reps"
                      value={ex.target_reps}
                      onChange={(e) => {
                        const next = [...days]
                        const exercises = [...day.exercises]
                        exercises[ei] = { ...ex, target_reps: e.target.value }
                        next[di] = { ...day, exercises }
                        setDays(next)
                      }}
                    />
                  </div>
                ))}
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    const next = [...days]
                    next[di] = { ...day, exercises: [...day.exercises, emptyExercise()] }
                    setDays(next)
                  }}
                >
                  Add exercise
                </button>
              </fieldset>
            ))}

            <button
              type="button"
              className="secondary"
              onClick={() => setDays([...days, emptyDay(days.length + 1)])}
            >
              Add day
            </button>

            <div className="row">
              <button type="submit" disabled={busy}>
                {busy ? 'Saving…' : 'Save plan'}
              </button>
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={() => {
                  setEditing(false)
                  void load()
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        ) : !program ? (
          <div className="empty-plan">
            <p>No active plan yet — ask Guide in chat, or create one here.</p>
            <button type="button" onClick={startCreate}>
              Create plan
            </button>
          </div>
        ) : (
          <>
            <div className="plan-meta">
              <span className={`status ${program.status}`}>{program.status}</span>
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
              <button type="button" onClick={startEdit}>
                Edit / replace plan
              </button>
            </div>
            {program.days.map((d) => (
              <section key={d.id ?? d.day_index} className="plan-day-view">
                <h2>
                  Day {d.day_index}
                  {d.label ? ` · ${d.label}` : ''}
                  {d.scheduled_date ? ` · ${d.scheduled_date}` : ''}
                </h2>
                <ul className="set-list">
                  {d.exercises.map((e) => (
                    <li key={e.id ?? `${e.canonical_name}-${e.order_index}`}>
                      <strong>{e.canonical_name}</strong>
                      {e.target_sets != null || e.target_reps
                        ? ` · ${e.target_sets ?? '?'}×${e.target_reps ?? '?'}`
                        : ''}
                      {e.notes ? ` — ${e.notes}` : ''}
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
