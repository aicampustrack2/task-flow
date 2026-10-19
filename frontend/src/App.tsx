import { useEffect, useState } from 'react'

type ApiStatus = 'checking' | 'ok' | 'error'

function App() {
  const [status, setStatus] = useState<ApiStatus>('checking')

  useEffect(() => {
    fetch('/api/health')
      .then((res) => setStatus(res.ok ? 'ok' : 'error'))
      .catch(() => setStatus('error'))
  }, [])

  return (
    <main>
      <h1>task-flow</h1>
      <p>
        API 연결:{' '}
        {status === 'checking' && '확인 중...'}
        {status === 'ok' && '연결됨'}
        {status === 'error' && '연결하지 못했습니다'}
      </p>
    </main>
  )
}

export default App
