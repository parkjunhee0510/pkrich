# Data Collection

## Sources

### Primary

* yfinance
* RSS feeds
* DuckDuckGo

### Optional

* FMP
* Finnhub
* Polygon
* SEC EDGAR

## Fallback Strategy

* Primary → Secondary → Tertiary sources
* Each source must degrade gracefully

## Requirements

### Reliability

* Retry on failure
* Do not crash pipeline

### Rate Limiting

* Respect API limits
* Add delays between calls

### Normalization

* Convert all inputs into structured format
* Ensure consistency across sources

## Rules

* No coupling with analyzer
* No assumptions about API stability
* Parsing logic must remain isolated
