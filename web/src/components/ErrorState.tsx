export function ErrorState({ message }: { message: string }) {
  return (
    <div className="error-state">
      <div className="error-state-icon">⚠️</div>
      <h3>데이터를 불러올 수 없습니다</h3>
      <p>서버 통신 중 문제가 발생했거나 데이터를 파싱할 수 없습니다.</p>
      <div className="error-state-detail">{message}</div>
      <button onClick={() => window.location.reload()}>다시 시도</button>
    </div>
  )
}
