import type { NewsReference } from '../types'
import { SecFilingBadges } from './SecFilingBadges'

export function NewsItem({ item, summary }: { item: NewsReference; summary?: string }) {
  const filingTag = extractSecFilingTag(item)
  const displayTitle = summary || stripSecFilingTag(item.title)

  return (
    <li className="news-item">
      {filingTag && <SecFilingBadges tags={[filingTag]} />}
      {item.link ? (
        <a href={item.link} target="_blank" rel="noopener noreferrer">
          {displayTitle}
        </a>
      ) : (
        <span>{displayTitle}</span>
      )}
      <span className="news-meta">
        {item.source && ` · ${item.source}`}
        {item.published_at && ` (${item.published_at})`}
      </span>
    </li>
  )
}

function extractSecFilingTag(item: NewsReference): string {
  if ((item.source || '').trim().toLowerCase() !== 'sec edgar') {
    return ''
  }
  const match = item.title.match(/^\[([^\]]+)\]\s*(.+)$/)
  return match ? match[1].trim() : ''
}

function stripSecFilingTag(title: string): string {
  const match = title.match(/^\[([^\]]+)\]\s*(.+)$/)
  return match ? match[2].trim() : title
}
