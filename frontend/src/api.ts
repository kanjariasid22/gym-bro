const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export type Unit = 'kg' | 'lbs'
export type SessionStatus = 'active' | 'completed' | 'cancelled'
export type AgentMode = 'guide' | 'trainer'
export type ProgramStatus = 'active' | 'archived'

export interface PlannedExercise {
  id?: number
  order_index: number
  raw_name: string
  canonical_name: string
  normalized_key?: string
  target_sets: number | null
  target_reps: string | null
  notes: string | null
}

export interface ProgramDay {
  id?: number
  day_index: number
  label: string | null
  scheduled_date: string | null
  exercises: PlannedExercise[]
}

export interface Program {
  id: number
  status: ProgramStatus | string
  goals: string | null
  end_date: string | null
  notes: string | null
  created_at: string
  updated_at: string
  archived_at?: string | null
  days: ProgramDay[]
}

export interface ProgramSummary {
  id: number
  status: ProgramStatus | string
  goals: string | null
  end_date: string | null
  created_at: string
  updated_at: string
  archived_at?: string | null
}

export interface ProgramPut {
  goals?: string | null
  end_date?: string | null
  notes?: string | null
  days: Array<{
    day_index: number
    label?: string | null
    scheduled_date?: string | null
    exercises: Array<{
      raw_name: string
      canonical_name?: string | null
      target_sets?: number | null
      target_reps?: string | null
      notes?: string | null
      order_index?: number
    }>
  }>
}

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

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  mode: AgentMode | null
  created_at: string
}

export interface ChatResponse {
  reply: string
  mode: string
  intent?: string
  tool_results: unknown[]
  ui_hints: {
    mode?: string
    active_session?: { id: number; status: string; started_at?: string } | null
    sets?: Array<{
      id: number
      canonical_name: string
      set_index: number
      weight: number
      unit: string
      reps: number
    }>
  }
  handoff_summary?: string | null
}

export interface CompleteResponse {
  session: WorkoutSession
  handoff: ChatResponse | null
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
  health: () =>
    request<{ status: string; groq_configured: boolean; memory_backend?: string }>('/health'),
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
    request<CompleteResponse>(`/sessions/${id}/complete`, {
      method: 'POST',
      body: JSON.stringify({ run_handoff: true }),
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
    body: Partial<{
      raw_name: string
      weight: number
      unit: Unit
      reps: number
      notes: string | null
    }>,
  ) =>
    request<SetLog>(`/sets/${setId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  deleteSet: (setId: number) => request<void>(`/sets/${setId}`, { method: 'DELETE' }),
  getChatMessages: (before?: number, limit = 30) => {
    const qs = new URLSearchParams({ limit: String(limit) })
    if (before != null) qs.set('before', String(before))
    return request<ChatMessage[]>(`/chat/messages?${qs}`)
  },
  postChat: (message: string) =>
    request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),
  getProgram: () => request<Program | null>('/program'),
  putProgram: (body: ProgramPut) =>
    request<Program>('/program', { method: 'PUT', body: JSON.stringify(body) }),
  listPrograms: () => request<ProgramSummary[]>('/programs'),
  getProgramById: (id: number) => request<Program>(`/programs/${id}`),
}
