import { useEffect, useState } from 'react'
import { changeStatus, deleteTask, listTasks, updateTask } from './api'
import Board from './components/Board'
import TaskForm from './components/TaskForm'
import type { Status, Task } from './types'

type Load = { state: 'loading' } | { state: 'error'; message: string } | { state: 'ready'; tasks: Task[] }

function App() {
  const [load, setLoad] = useState<Load>({ state: 'loading' })

  useEffect(() => {
    listTasks()
      .then((tasks) => setLoad({ state: 'ready', tasks }))
      .catch(() => setLoad({ state: 'error', message: '카드를 불러오지 못했습니다.' }))
  }, [])

  // 수정·삭제는 API가 성공으로 응답한 뒤에만 목록에 반영한다. (D-004)
  // 상태 변경은 응답을 기다리지 않고 먼저 반영한다. (연습용으로 D-004와 다르게 둠)
  function withTasks(fn: (tasks: Task[]) => Task[]) {
    setLoad((prev) => (prev.state === 'ready' ? { state: 'ready', tasks: fn(prev.tasks) } : prev))
  }

  async function handleChangeStatus(id: number, status: Status) {
    withTasks((tasks) => tasks.map((t) => (t.id === id ? { ...t, status } : t)))
    await changeStatus(id, status)
  }

  async function handleUpdate(id: number, input: { title: string; description: string }) {
    const saved = await updateTask(id, input)
    withTasks((tasks) => tasks.map((t) => (t.id === id ? saved : t)))
  }

  async function handleDelete(id: number) {
    await deleteTask(id)
    withTasks((tasks) => tasks.filter((t) => t.id !== id))
  }

  return (
    <main>
      <h1>task-flow</h1>
      {load.state === 'loading' && <p>불러오는 중...</p>}
      {/* 불러오지 못했을 때는 빈 보드처럼 보여 주지 않는다. */}
      {load.state === 'error' && <p role="alert">{load.message}</p>}
      {load.state === 'ready' && (
        <>
          <TaskForm onCreated={(task) => withTasks((tasks) => [...tasks, task])} />
          <Board
            tasks={load.tasks}
            onChangeStatus={handleChangeStatus}
            onUpdate={handleUpdate}
            onDelete={handleDelete}
          />
        </>
      )}
    </main>
  )
}

export default App
