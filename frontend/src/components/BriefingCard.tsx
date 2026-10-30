import { EMPTY, FAILED, useBriefing } from '../useBriefing'
import type { Task } from '../types'

const NUMBERS = ['①', '②', '③']

// [오늘 브리핑] 버튼과 그 아래 카드 한 장. 제목은 id 로 지금 목록에서 찾는다.
export default function BriefingCard({ tasks }: { tasks: Task[] }) {
  const { busy, briefing, error, run, close } = useBriefing()

  const titleOf = (id: number) => tasks.find((t) => t.id === id)?.title
  // 지금 목록에 없는 id(그 사이 삭제된 Task)는 건너뛴다.
  const picks = (briefing?.top3 ?? []).flatMap((p) => {
    const title = titleOf(p.id)
    return title === undefined ? [] : [{ id: p.id, title, reason: p.reason }]
  })
  const later = (briefing?.later ?? []).flatMap((id) => {
    const title = titleOf(id)
    return title === undefined ? [] : [{ id, title }]
  })

  let body = null
  if (error) {
    body = <p role="alert">{error}</p>
  } else if (briefing && briefing.top3.length === 0) {
    body = <p role="status">{EMPTY}</p>
  } else if (briefing && picks.length === 0) {
    body = <p role="alert">{FAILED}</p>
  } else if (briefing) {
    body = (
      <section className="briefing-card" aria-label="오늘 브리핑">
        <div className="briefing-head">
          <h2>먼저 할 일</h2>
          <button type="button" onClick={close}>
            닫기
          </button>
        </div>
        <ol className="briefing-list">
          {picks.map((p, i) => (
            <li key={p.id}>
              <span className="briefing-no">{NUMBERS[i]}</span> {p.title} — {p.reason}
            </li>
          ))}
        </ol>
        {later.length > 0 && (
          <>
            <h3>미뤄도 되는 일</h3>
            <ul className="briefing-list">
              {later.map((t) => (
                <li key={t.id}>{t.title}</li>
              ))}
            </ul>
          </>
        )}
        <p className="briefing-cheer">{briefing.cheer}</p>
      </section>
    )
  }

  return (
    <div className="briefing">
      <button type="button" onClick={run} disabled={busy}>
        {busy ? '만드는 중…' : '오늘 브리핑'}
      </button>
      {body}
    </div>
  )
}
