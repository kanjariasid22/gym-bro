import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { ChatPage } from './pages/ChatPage'
import { HistoryPage } from './pages/HistoryPage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { SessionDetailPage } from './pages/SessionDetailPage'

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="auth-page">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

function GuestOnly({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="auth-page">Loading…</div>
  if (user) return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <GuestOnly>
            <LoginPage />
          </GuestOnly>
        }
      />
      <Route
        path="/register"
        element={
          <GuestOnly>
            <RegisterPage />
          </GuestOnly>
        }
      />
      <Route
        path="/"
        element={
          <Protected>
            <ChatPage />
          </Protected>
        }
      />
      <Route
        path="/history"
        element={
          <Protected>
            <HistoryPage />
          </Protected>
        }
      />
      <Route
        path="/history/:id"
        element={
          <Protected>
            <SessionDetailPage />
          </Protected>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
