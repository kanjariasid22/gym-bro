const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export type Unit = 'kg' | 'lbs'
export type SessionStatus = 'active' | 'completed' | 'cancelled'

export interface User {
  id: number
  email: string
  unit_preference: Unit
  created_at: string
}

export interface WorkoutSession {
  id: number
  status: SessionStatus
  started_at: string
  ended_at: string | null
  summary: string | null
}

export interface SetLog {
  id: number
  session_id: number
  raw_name: string
  canonical_name: string
  normalized_key: string
  set_index: number
  weight: number
  unit: Unit
  reps: number
  notes: string | null
  created_at: string
  updated_at: string
}

export interface SessionDetail extends WorkoutSession {
  set_logs: SetLog[]
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: 'include',
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = data.detail ?? JSON.stringify(data)
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }

  if (res.status === 204) {
    return undefined as T
  }

  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; groq_configured: boolean }>('/health'),
  me: () => request<User>('/me'),
  register: (email: string, password: string, unit_preference: Unit = 'kg') =>
    request<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, unit_preference }),
    }),
  login: (email: string, password: string) =>
    request<User>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
  getActiveSession: () => request<WorkoutSession | null>('/sessions/active'),
  listSessions: () => request<WorkoutSession[]>('/sessions'),
  getSession: (id: number) => request<SessionDetail>(`/sessions/${id}`),
  startSession: () => request<WorkoutSession>('/sessions/start', { method: 'POST' }),
  completeSession: (id: number) =>
    request<WorkoutSession>(`/sessions/${id}/complete`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),
  cancelSession: (id: number) =>
    request<WorkoutSession>(`/sessions/${id}/cancel`, { method: 'POST' }),
  createSet: (
    sessionId: number,
    body: { raw_name: string; weight: number; unit: Unit; reps: number; notes?: string },
  ) =>
    request<SetLog>(`/sessions/${sessionId}/sets`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  patchSet: (
    setId: number,
    body: Partial<{ raw_name: string; weight: number; unit: Unit; reps: number; notes: string | null }>,
  ) =>
    request<SetLog>(`/sets/${setId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  deleteSet: (setId: number) => request<void>(`/sets/${setId}`, { method: 'DELETE' }),
}
