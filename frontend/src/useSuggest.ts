import { useRef, useState } from 'react'
import { ApiError, suggestTask } from './api'
import type { Suggestion } from './types'

const UNAVAILABLE = '지금은 AI 제안을 쓸 수 없습니다. - 직접 입력을 주세요.'
const FAILED = '제안을 못 받았습니다. 다시 제안 버튼을 눌러 보세요.'

function messageFor(err: unknown): string {
  if (err instanceof ApiError && err.status === 503) return UNAVAILABLE
  if (err instanceof ApiError && err.status === 502) return FAILED
  return err instanceof Error ? err.message : FAILED
}

// 제안만 받아 입력란을 채운다. 저장은 하지 않는다. 등록·저장은 사용자가 따로 누른다.
// 제안 상태는 저장 오류와 따로 두어, 제안이 실패해도 등록·저장 흐름에 영향이 없다.
export function useSuggest(
  getInput: () => { title: string; description: string },
  onSuggested: (suggestion: Suggestion) => void,
) {
  const [busy, setBusy] = useState(false)
  const [reason, setReason] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  // 요청마다 번호를 매겨, 그 사이에 등록·취소로 폼이 바뀌었으면 늦게 온 응답을 버린다.
  const latest = useRef(0)

  function reset() {
    latest.current += 1
    setBusy(false)
    setReason(null)
    setError(null)
  }

  async function suggest() {
    const input = getInput()
    // 편의 검사. 최종 판단은 API가 한다. (D-003)
    if (!input.title.trim()) {
      setReason(null)
      setError('제목을 입력하세요.')
      return
    }
    const mine = ++latest.current
    setError(null)
    setReason(null)
    setBusy(true)
    try {
      const suggestion = await suggestTask(input)
      if (mine !== latest.current) return
      onSuggested(suggestion)
      setReason(suggestion.reason)
    } catch (err) {
      if (mine !== latest.current) return
      setError(messageFor(err))
    } finally {
      if (mine === latest.current) setBusy(false)
    }
  }

  return { busy, reason, error, suggest, reset }
}

export type Suggest = ReturnType<typeof useSuggest>
