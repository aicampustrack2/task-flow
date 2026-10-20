import type { Task } from '../types'

export default function TaskCard({ task }: { task: Task }) {
  return (
    <li className="card">
      <strong>{task.title}</strong>
      {task.description && <p>{task.description}</p>}
    </li>
  )
}
