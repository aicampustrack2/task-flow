import { COLUMNS, type Task } from '../types'
import TaskCard from './TaskCard'

export default function Board({ tasks }: { tasks: Task[] }) {
  return (
    <div className="board">
      {COLUMNS.map((col) => (
        <section key={col.status} className="column">
          <h2>{col.label}</h2>
          <ul>
            {tasks
              .filter((t) => t.status === col.status)
              .map((t) => (
                <TaskCard key={t.id} task={t} />
              ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
