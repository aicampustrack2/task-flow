import type { Suggest } from '../useSuggest'

export function SuggestButton({ suggest }: { suggest: Suggest }) {
  return (
    <div className="suggest-bar">
      <button type="button" onClick={suggest.suggest} disabled={suggest.busy}>
        AI 제안
      </button>
      {suggest.busy && <span role="status">제안을 받는 중...</span>}
    </div>
  )
}

export function SuggestNote({ suggest }: { suggest: Suggest }) {
  if (suggest.error) return <p role="alert">{suggest.error}</p>
  if (suggest.reason) return <p className="suggest-reason">이유: {suggest.reason}</p>
  return null
}
