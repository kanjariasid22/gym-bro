import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { api, type ChatMessage, type SetLog, type WorkoutSession } from '../api'
import { useAuth } from '../AuthContext'
import { AppNav } from '../components/AppNav'

export function ChatPage() {
  const { user } = useAuth()
  const [session, setSession] = useState<WorkoutSession | null>(null)
  const [sets, setSets] = useState<SetLog[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [loadingEarlier, setLoadingEarlier] = useState(false)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  const [rawName, setRawName] = useState('')
  const [weight, setWeight] = useState('')
  const [reps, setReps] = useState('')
  const [notes, setNotes] = useState('')

  const mode = session?.status === 'active' ? 'trainer' : 'guide'

  const refreshSession = useCallback(async () => {
    const active = await api.getActiveSession()
    setSession(active)
    if (active) {
      const detail = await api.getSession(active.id)
      setSets(detail.set_logs)
    } else {
      setSets([])
    }
  }, [])

  const loadMessages = useCallback(async () => {
    const rows = await api.getChatMessages()
    setMessages(rows)
  }, [])

  useEffect(() => {
    void (async () => {
      try {
        await Promise.all([refreshSession(), loadMessages()])
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load')
      }
    })()
  }, [refreshSession, loadMessages])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function loadEarlier() {
    if (!messages.length) return
    setLoadingEarlier(true)
    setError(null)
    try {
      const earlier = await api.getChatMessages(messages[0].id)
      setMessages((prev) => [...earlier, ...prev])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Load earlier failed')
    } finally {
      setLoadingEarlier(false)
    }
  }

  function applyHints(hints: {
    active_session?: { id: number; status: string; started_at?: string } | null
    sets?: Array<{
      id: number
      canonical_name: string
      set_index: number
      weight: number
      unit: string
      reps: number
    }>
  }) {
    if (hints.active_session) {
      setSession({
        id: hints.active_session.id,
        status: hints.active_session.status as WorkoutSession['status'],
        started_at: hints.active_session.started_at ?? new Date().toISOString(),
        ended_at: null,
        summary: null,
      })
    } else {
      setSession(null)
    }
    if (hints.sets) {
      setSets(
        hints.sets.map((s) => ({
          id: s.id,
          session_id: hints.active_session?.id ?? 0,
          raw_name: s.canonical_name,
          canonical_name: s.canonical_name,
          normalized_key: s.canonical_name.toLowerCase(),
          set_index: s.set_index,
          weight: s.weight,
          unit: s.unit as SetLog['unit'],
          reps: s.reps,
          notes: null,
          created_at: '',
          updated_at: '',
        })),
      )
    }
  }

  async function sendChat(e: FormEvent) {
    e.preventDefault()
    const text = draft.trim()
    if (!text) return
    setBusy(true)
    setError(null)
    setDraft('')
    const optimistic: ChatMessage = {
      id: -Date.now(),
      role: 'user',
      content: text,
      mode: null,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, optimistic])
    try {
      const res = await api.postChat(text)
      applyHints(res.ui_hints || {})
      await loadMessages()
      await refreshSession()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Chat failed')
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id))
      setDraft(text)
    } finally {
      setBusy(false)
    }
  }

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
      const res = await api.completeSession(session.id)
      setSession(null)
      setSets([])
      await loadMessages()
      if (res.handoff?.reply) {
        // messages already persisted server-side
      }
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
      <AppNav
        extra={
          <div className={`mode-chip ${mode}`}>
            {mode === 'trainer' ? 'Trainer · live' : 'Guide'}
          </div>
        }
      />

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
          <button
            type="button"
            className="secondary"
            disabled={loadingEarlier || messages.length === 0}
            onClick={() => void loadEarlier()}
          >
            {loadingEarlier ? 'Loading…' : 'Load earlier'}
          </button>
          <div className="chat-log">
            {messages.length === 0 && (
              <p className="muted">
                Say hi to Guide — share goals and a plan end date, or paste an existing plan.
              </p>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`bubble ${m.role}`}>
                {m.role === 'assistant' && m.mode && (
                  <span className={`mode-badge ${m.mode}`}>{m.mode}</span>
                )}
                <p>{m.content}</p>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
          <form className="chat-compose" onSubmit={sendChat}>
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={
                mode === 'trainer'
                  ? 'e.g. lat pd 3x10 @ 50kg'
                  : 'Talk to Guide about your plan…'
              }
              disabled={busy}
            />
            <button type="submit" disabled={busy || !draft.trim()}>
              Send
            </button>
          </form>
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
                <h3>Log a set (manual)</h3>
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
