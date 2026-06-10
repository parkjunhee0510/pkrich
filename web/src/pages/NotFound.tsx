import { useEffect } from 'react'
import { Link } from 'react-router-dom'

export function NotFound() {
  useEffect(() => {
    document.title = '404 · Stock Research'
    return () => { document.title = 'Stock Research' }
  }, [])

  return (
    <div className="not-found-page">
      <div className="not-found-code">404</div>
      <h1>페이지를 찾을 수 없습니다</h1>
      <p>요청하신 경로가 존재하지 않거나 이동되었습니다.</p>
      <Link to="/">← 대시보드로 돌아가기</Link>
    </div>
  )
}
