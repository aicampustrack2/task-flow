import type { Task } from './types'

// /api 는 Vite 프록시가 로컬 API 서버로 넘긴다.
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, init)
  } catch {
    throw new Error('서버에 연결하지 못했습니다.')
  }
  if (!res.ok) {
    let message = '요청을 처리하지 못했습니다.'
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // 본문이 없으면 기본 문구를 쓴다.
    }
    throw new Error(message)
  }
  return res.json() as Promise<T>
}

export function listTasks(): Promise<Task[]> {
  return request<Task[]>('/tasks')
}

export function createTask(input: { title: string; description: string }): Promise<Task> {
  return request<Task>('/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}
