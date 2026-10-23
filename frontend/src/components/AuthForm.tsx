import { useState, type FormEvent } from 'react'
import { login, signup } from '../api'
import type { User } from '../types'

type Mode = 'login' | 'signup'

export default function AuthForm({
  notice,
  onLoggedIn,
}: {
  notice?: string
  onLoggedIn: (user: User) => void
}) {
  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function switchMode(next: Mode) {
    setMode(next)
    setError(null)
    setInfo(null)
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setInfo(null)
    setBusy(true)
    try {
      if (mode === 'login') {
        onLoggedIn(await login({ username, password }))
        return
      }
      // 가입해도 자동 로그인하지 않는다. (D-026)
      await signup({ username, password })
      setPassword('')
      setMode('login')
      setInfo('가입했습니다. 로그인하세요.')
    } catch (err) {
      setError(err instanceof Error ? err.message : '요청을 처리하지 못했습니다.')
    } finally {
      setBusy(false)
    }
  }

  const isLogin = mode === 'login'
  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      <h2>{isLogin ? '로그인' : '가입'}</h2>
      {notice && <p role="status">{notice}</p>}
      {info && <p role="status">{info}</p>}
      <input
        aria-label="아이디(이메일)"
        placeholder="아이디 (이메일)"
        type="email"
        autoComplete="username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
      />
      <input
        aria-label="비밀번호"
        placeholder={isLogin ? '비밀번호' : '비밀번호 (8자 이상)'}
        type="password"
        autoComplete={isLogin ? 'current-password' : 'new-password'}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <button type="submit" disabled={busy}>
        {busy ? '처리 중...' : isLogin ? '로그인' : '가입'}
      </button>
      {error && <p role="alert">{error}</p>}
      <button type="button" className="link" onClick={() => switchMode(isLogin ? 'signup' : 'login')}>
        {isLogin ? '계정이 없으면 가입' : '이미 계정이 있으면 로그인'}
      </button>
    </form>
  )
}
