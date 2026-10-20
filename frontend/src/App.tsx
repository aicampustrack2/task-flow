import { useEffect, useState } from 'react'
import { listTasks } from './api'
import Board from './components/Board'
import TaskForm from './components/TaskForm'
import type { Task } from './types'

type Load = { state: 'loading' } | { state: 'error'; message: string } | { state: 'ready'; tasks: Task[] }

function App() {
  const [load, setLoad] = useState<Load>({ state: 'loading' })

  useEffect(() => {
    listTasks()
      .then((tasks) => setLoad({ state: 'ready', tasks }))
      .catch(() => setLoad({ state: 'error', message: '카드를 불러오지 못했습니다.' }))
  }, [])

  return (
    <main>
      <h1>task-flow</h1>
      {load.state === 'loading' && <p>불러오는 중...</p>}
      {/* 불러오지 못했을 때는 빈 보드처럼 보여 주지 않는다. */}
      {load.state === 'error' && <p role="alert">{load.message}</p>}
      {load.state === 'ready' && (
        <>
          <TaskForm onCreated={(task) => setLoad({ state: 'ready', tasks: [...load.tasks, task] })} />
          <Board tasks={load.tasks} />
        </>
      )}
    </main>
  )
}

export default App
