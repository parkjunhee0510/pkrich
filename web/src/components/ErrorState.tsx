import { Button } from './ui/Button'

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="error-state" role="alert" aria-live="assertive">
      <div className="error-state-icon" aria-hidden="true">주의</div>
      <h3>데이터를 불러오지 못했습니다.</h3>
      <p>서버 응답에 문제가 있거나 출력 파일이 아직 준비되지 않았습니다.</p>
      <div className="error-state-detail">{message}</div>
      <Button onClick={() => window.location.reload()} aria-label="현재 페이지 데이터를 다시 불러오기">
        다시 시도
      </Button>
    </div>
  )
}
