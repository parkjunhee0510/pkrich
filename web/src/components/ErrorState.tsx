export function ErrorState({ message }: { message: string }) {
  return (
    <div className="error-state">
      <div className="error-state-icon">주의</div>
      <h3>데이터를 불러오지 못했습니다</h3>
      <p>서버 통신에 문제가 있거나 출력 파일을 아직 찾지 못했습니다.</p>
      <div className="error-state-detail">{message}</div>
      <button onClick={() => window.location.reload()}>다시 시도</button>
    </div>
  )
}
