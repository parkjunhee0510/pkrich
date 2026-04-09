function filingTagClass(tag: string): string {
  const normalized = tag.trim()
  if (normalized === '실적') return 'filing-earnings'
  if (normalized === '배당') return 'filing-dividend'
  if (normalized === '주주총회') return 'filing-shareholder'
  return 'filing-general'
}

export function SecFilingBadges({ tags }: { tags: string[] }) {
  if (tags.length === 0) {
    return null
  }

  return (
    <div className="filing-badges">
      {tags.map((tag) => (
        <span key={tag} className={`filing-badge ${filingTagClass(tag)}`}>
          [{tag}]
        </span>
      ))}
    </div>
  )
}
