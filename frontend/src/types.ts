export type Status = 'TODO' | 'IN_PROGRESS' | 'DONE'

export type Priority = 'LOW' | 'NORMAL' | 'HIGH'

export interface Task {
  id: number
  title: string
  description: string
  status: Status
  priority: Priority
  // YYYY-MM-DD. 마감일이 없으면 null. 날짜는 문자열 그대로 쓰고 브라우저에서 계산하지 않는다.
  due_date: string | null
  // 서버가 목록을 줄 때 계산한 값이다. (저장하는 값이 아니다)
  is_overdue: boolean
}

// 등록과 수정이 함께 쓰는 입력. 마감일을 비우면 null.
export interface TaskInput {
  title: string
  description: string
  priority: Priority
  due_date: string | null
}

// AI 제안. 저장된 값이 아니라 입력란에 채울 값이다. due_date 가 null 이면 마감일 없음.
export interface Suggestion {
  priority: Priority
  due_date: string | null
  reason: string
}

// 오늘 브리핑. 보여 주기만 하고 저장하지 않는다. top3 는 먼저 할 일, later 는 미뤄도 되는 Task id.
export interface BriefingPick {
  id: number
  reason: string
}

export interface Briefing {
  top3: BriefingPick[]
  later: number[]
  cheer: string
}

export interface User {
  id: number
  username: string
}

// 선택지 순서와 화면 표시 이름. 저장값은 LOW · NORMAL · HIGH.
export const PRIORITIES: { priority: Priority; label: string }[] = [
  { priority: 'HIGH', label: '높음' },
  { priority: 'NORMAL', label: '보통' },
  { priority: 'LOW', label: '낮음' },
]

// 열 순서와 화면 표시. 저장값은 DATA-MODEL.md 기준.
export const COLUMNS: { status: Status; label: string }[] = [
  { status: 'TODO', label: '할 일' },
  { status: 'IN_PROGRESS', label: '진행 중' },
  { status: 'DONE', label: '완료' },
]
