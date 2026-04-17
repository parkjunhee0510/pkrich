const LABELS: Record<string, string> = {
  Price: '가격',
  'Daily Change': '일간 등락률',
  'Market Cap': '시가총액',
  'Trailing P/E': '최근 12개월 PER',
  EPS: 'EPS (TTM)',
  '52W High': '52주 최고',
  '52W Low': '52주 최저',
  '50D SMA': '50일 이동평균',
  '200D SMA': '200일 이동평균',
  Volume: '거래량',
  '3M Avg Volume': '3개월 평균 거래량',
  'Price/Book': 'PBR',
  'Dividend Yield': '배당수익률',
  Sector: '섹터',
  'RS vs Sector ETF': '섹터 ETF 대비 상대강도',
}

export function DataSnapshot({ snapshot }: { snapshot: Record<string, string> }) {
  return (
    <table className="snapshot-table">
      <thead>
        <tr><th>항목</th><th>값</th></tr>
      </thead>
      <tbody>
        {Object.entries(snapshot).map(([key, value]) => (
          <tr key={key}>
            <td>{LABELS[key] ?? key}</td>
            <td>{value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
