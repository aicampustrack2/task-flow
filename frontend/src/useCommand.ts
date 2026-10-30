import { useEffect, useRef, useState } from 'react'
import { ApiError, changeStatus, createTask, runCommand, updateTask } from './api'
import type { CommandAction, Task } from './types'

export const MAX_LENGTH = 200
export const UNAVAILABLE = '지금은 시킬 수 없습니다'
export const FAILED = '알아듣지 못했습니다'

function messageFor(err: unknown): string {
  if (err instanceof ApiError && err.status === 503) return UNAVAILABLE
  if (err instanceof ApiError && err.status === 502) return FAILED
  // 422 는 서버가 준 이유 그대로, 연결 실패 등은 그 문구를 쓴다.
  return err instanceof Error ? err.message : FAILED
}

// 제안 한 줄. 제목은 id 로 지금 목록에서 찾는다. 목록에 없는 id(그 사이 삭제)는 null 이라 건너뛴다.
export interface Line {
  action: CommandAction
  title: string
  task: Task | null
}

export function toLines(actions: CommandAction[], tasks: Task[]): Line[] {
  return actions.flatMap((action): Line[] => {
    if (action.kind === 'add') {
      return action.title === null ? [] : [{ action, title: action.title, task: null }]
    }
    const task = tasks.find((t) => t.id === action.id)
    return task ? [{ action, title: task.title, task }] : []
  })
}

// 한 줄을 기존 API 로 한 번 반영한다. due 는 나머지 값을 지금 그대로 두고 마감일만 바꾼다.
async function apply({ action, task }: Line) {
  if (action.kind === 'add') {
    await createTask({
      title: action.title ?? '',
      description: '',
      priority: action.priority ?? 'NORMAL',
      due_date: action.due_date,
    })
  } else if (action.kind === 'due' && task) {
    await updateTask(task.id, {
      title: task.title,
      description: task.description,
      priority: task.priority,
      due_date: action.due_date,
    })
  } else if (action.kind === 'done' && task) {
    await changeStatus(task.id, 'DONE')
  }
}

// 제안만 받아 보여 준다. 사용자가 적용을 눌러야 기존 API 로 한 줄씩 반영한다.
// 상태는 Task 목록 · 등록 폼 · AI 제안 · 브리핑과 섞이지 않는다.
export function useCommand(getTasks: () => Task[], onApplied: () => void) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [applying, setApplying] = useState(false)
  const [lines, setLines] = useState<Line[] | null>(null)
  const [ask, setAsk] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  // 요청마다 번호를 매겨, 취소했거나 화면이 사라진 뒤에 늦게 온 응답을 버린다.
  const latest = useRef(0)

  useEffect(() => {
    return () => {
      latest.current += 1
    }
  }, [])

  function clearResult() {
    setLines(null)
    setAsk(null)
    setError(null)
  }

  function cancel() {
    latest.current += 1
    setBusy(false)
    clearResult()
  }

  async function send() {
    // 편의 검사. 최종 판단은 API가 한다. (D-003)
    if (!text.trim()) return
    const mine = ++latest.current
    clearResult()
    setBusy(true)
    try {
      const result = await runCommand(text)
      if (mine !== latest.current) return
      const next = toLines(result.actions, getTasks())
      if (next.length > 0) setLines(next)
      else setAsk(result.ask ?? FAILED)
    } catch (err) {
      if (mine !== latest.current) return
      setError(messageFor(err))
    } finally {
      if (mine === latest.current) setBusy(false)
    }
  }

  // 순서대로 한 번에 하나씩 반영한다. 실패하면 거기서 멈춘다.
  // 이미 반영된 것이 있을 수 있어 목록을 다시 받고 카드를 닫는다. (다시 적용하면 add 가 중복된다)
  async function applyAll() {
    if (!lines) return
    const mine = ++latest.current
    setApplying(true)
    setError(null)
    let done = 0
    let failure: string | null = null
    for (const line of lines) {
      try {
        await apply(line)
        done += 1
      } catch (err) {
        failure = `${done}개 적용했고 '${line.title}'은(는) 못 했습니다: ${messageFor(err)}`
        break
      }
    }
    if (done > 0) onApplied()
    if (mine !== latest.current) return
    setApplying(false)
    setLines(null)
    if (failure) {
      setError(failure)
    } else {
      setText('')
    }
  }

  return { text, setText, busy, applying, lines, ask, error, send, applyAll, cancel }
}
