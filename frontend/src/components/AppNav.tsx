import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../AuthContext'

export function AppNav({ extra }: { extra?: ReactNode }) {
  const { logout } = useAuth()
  return (
    <header className="topbar">
      <div className="brand">GymBro</div>
      {extra}
      <nav>
        <Link to="/">Chat</Link>
        <Link to="/plan">Plan</Link>
        <Link to="/history">History</Link>
        <button type="button" className="linkish" onClick={() => void logout()}>
          Log out
        </button>
      </nav>
    </header>
  )
}
