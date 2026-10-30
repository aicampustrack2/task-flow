import { MAX_LENGTH, useCommand } from '../useCommand'
import type { Line } from '../useCommand'
import type { Task } from '../types'

function describe({ action }: Line): string {
  if (action.kind === 'done') return '완료로'
  if (action.kind === 'due') return `마감을 ${action.due_date} 으로`
  return `새 카드 (우선순위 ${action.priority ?? 'NORMAL'} · 마감 ${action.due_date ?? '없음'})`
}

function titleOf(line: Line): string {
  // due 는 바뀌기 전 마감일을 함께 보여 준다.
  if (line.action.kind === 'due') return `${line.title}(지금 마감 ${line.task?.due_date ?? '없음'})`
  return line.title
}

// 입력란 하나와 [시키기] 단추, 그 아래 확인 카드 한 장. 확인하고 적용을 눌러야 반영된다.
export default function CommandBox({ tasks, onApplied }: { tasks: Task[]; onApplied: () => void }) {
  const c = useCommand(() => tasks, onApplied)
  const locked = c.busy || c.applying

  return (
    <div className="command">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          c.send()
        }}
      >
        <input
          type="text"
          aria-label="한 문장으로 시키기"
          maxLength={MAX_LENGTH}
          value={c.text}
          onChange={(e) => c.setText(e.target.value)}
          disabled={locked}
        />{' '}
        <button type="submit" disabled={locked || !c.text.trim()}>
          {c.busy ? '알아듣는 중…' : '시키기'}
        </button>
      </form>
      {c.error && <p role="alert">{c.error}</p>}
      {c.ask && <p role="status">{c.ask}</p>}
      {c.lines && (
        <section aria-label="제안 확인">
          <h2>이렇게 바꿀까요? {c.lines.length}개</h2>
          <ul>
            {c.lines.map((line, i) => (
              <li key={i}>
                {titleOf(line)} — {describe(line)}
              </li>
            ))}
          </ul>
          <button type="button" onClick={c.applyAll} disabled={c.applying}>
            {c.applying ? '적용하는 중…' : '적용'}
          </button>{' '}
          <button type="button" onClick={c.cancel} disabled={c.applying}>
            취소
          </button>
        </section>
      )}
    </div>
  )
}
