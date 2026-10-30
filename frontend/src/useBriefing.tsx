import { useEffect, useRef, useState } from 'react'
import { ApiError, getBriefing } from './api'
import type { Briefing } from './types'

export const UNAVAILABLE = '지금은 브리핑을 쓸 수 없습니다'
export const FAILED = '브리핑을 받지 못했습니다'
export const EMPTY = '오늘은 비어 있어요'

function messageFor(err: unknown): string {
  if (err instanceof ApiError && err.status === 503) return UNAVAILABLE
  if (err instanceof ApiError && err.status === 502) return FAILED
  return err instanceof Error ? err.message : FAILED
}

// 브리핑만 받아 보여 준다. 저장하지 않고 Task 목록 · 등록 폼 · AI 제안 상태와 섞이지 않는다.
export function useBriefing() {
  const [busy, setBusy] = useState(false)
  const [briefing, setBriefing] = useState<Briefing | null>(null)
  const [error, setError] = useState<string | null>(null)
  // 요청마다 번호를 매겨, 닫았거나 화면이 사라진 뒤에 늦게 온 응답을 버린다.
  const latest = useRef(0)

  useEffect(() => {
    return () => {
      latest.current += 1
    }
  }, [])

  function close() {
    latest.current += 1
    setBusy(false)
    setBriefing(null)
    setError(null)
  }

  async function run() {
    const mine = ++latest.current
    setBriefing(null)
    setError(null)
    setBusy(true)
    try {
      const result = await getBriefing()
      if (mine !== latest.current) return
      setBriefing(result)
    } catch (err) {
      if (mine !== latest.current) return
      setError(messageFor(err))
    } finally {
      if (mine === latest.current) setBusy(false)
    }
  }

  return { busy, briefing, error, run, close }
}
