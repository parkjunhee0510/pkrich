from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.output.json_export import write_json_outputs
from src.output.markdown import append_price_history, render_daily_markdown, render_ticker_markdown
from src.types import NewsItem, PortfolioPosition, PortfolioSummary, TickerAnalysis


def _sample_analysis() -> TickerAnalysis:
    return TickerAnalysis(
        ticker='AAPL',
        name='Apple Inc.',
        date='2026-04-08',
        summary='샘플 요약입니다.',
        key_news=[
            '애플 실적이 예상치를 웃돌았습니다.',
            '애플의 신제품 기대감이 이어지고 있습니다.',
            '애플이 SEC에 분기 실적 관련 보고서를 제출했습니다.',
            '애플의 오래된 기사입니다.',
        ],
        news_references=[
            NewsItem(
                title='Apple earnings beat expectations',
                source='Reuters',
                published_at='2026-04-08',
                link='https://example.com/apple-earnings',
            ),
            NewsItem(
                title='Apple product preview gains attention',
                source='Yahoo Finance',
                published_at='2026-04-07',
                link='https://example.com/apple-preview',
            ),
            NewsItem(
                title='[실적] Apple Inc., 10-Q 분기 실적 관련 보고서를 SEC에 제출',
                source='SEC EDGAR',
                published_at='2026-04-06',
                link='https://example.com/apple-sec-10q',
            ),
            NewsItem(
                title='Apple legacy milestone feature',
                source='Reuters',
                published_at='2025-01-30',
                link='https://example.com/apple-old',
            ),
        ],
        financial_highlights=['시가총액: 1.00T', '최근 12개월 PER: 25.00'],
        risks_or_watchpoints=['경쟁 심화 여부 점검'],
        signal_or_takeaway='관찰 지속',
        data_snapshot={
            'Price': '100.00 USD',
            'Daily Change': '+1.23%',
            'Market Cap': '1.00T',
            'Trailing P/E': '25.00',
            'EPS': '6.10',
            '52W High': '110.00',
            '52W Low': '80.00',
            '50D SMA': '98.50',
            '200D SMA': '95.10',
            'Volume': '12.30M',
            '3M Avg Volume': '18.50M',
            'Price/Book': '8.50',
            'Dividend Yield': '0.45%',
            'Sector': 'Technology',
        },
        fundamentals={
            'market_cap': '1.00T',
            'trailing_pe': '25.00',
            'eps': '6.10',
            'price_to_book': '8.50',
            'dividend_yield': '0.45%',
            'volume': '12.30M',
            'avg_volume_3m': '18.50M',
            '52w_high': '110.00',
            '52w_low': '80.00',
        },
        quarterly_financials=[
            {'quarter': '2025-Q4', 'revenue': '120.00B', 'operating_income': '35.00B', 'eps': '2.10'},
            {'quarter': '2025-Q3', 'revenue': '118.00B', 'operating_income': '33.00B', 'eps': '1.98'},
            {'quarter': '2025-Q2', 'revenue': '115.00B', 'operating_income': '31.00B', 'eps': '1.90'},
            {'quarter': '2025-Q1', 'revenue': '110.00B', 'operating_income': '30.00B', 'eps': '1.80'},
            {'quarter': '2024-Q4', 'revenue': '100.00B', 'operating_income': '30.00B', 'eps': '1.80'},
            {'quarter': '2024-Q3', 'revenue': '98.00B', 'operating_income': '28.00B', 'eps': '1.70'},
        ],
        upcoming_events=[
            {'type': 'earnings', 'label': '실적 발표', 'date': '2026-04-14', 'days_until': '6'},
        ],
        news_tone={'label': 'bullish', 'score': 1.0},
    )


class OutputTests(unittest.TestCase):
    def test_render_daily_markdown_includes_key_sections_and_schedule(self) -> None:
        content = render_daily_markdown(
            [_sample_analysis()],
            date(2026, 4, 8),
            market_overview=[{'label': 'S&P 500', 'symbol': '^GSPC', 'price': '5,234.18', 'change': '+0.45%'}],
            portfolio_summary=PortfolioSummary(
                positions=[
                    PortfolioPosition(
                        ticker='AAPL',
                        shares=10,
                        avg_cost=90.0,
                        currency='USD',
                        market_price=100.0,
                        market_value=1000.0,
                        cost_basis=900.0,
                        unrealized_pnl=100.0,
                        unrealized_return_pct=11.11,
                    )
                ],
                total_market_value=1000.0,
                total_cost_basis=900.0,
                total_unrealized_pnl=100.0,
                total_unrealized_return_pct=11.11,
            ),
        )

        self.assertIn('# 일일 리서치 - 2026-04-08', content)
        self.assertIn('## 시장 개요', content)
        self.assertIn('## 포트폴리오 현황', content)
        self.assertIn('## 주요 뉴스 링크', content)
        self.assertIn('## SEC 공시', content)
        self.assertIn('## 다가오는 일정', content)
        self.assertNotIn('## 주요 움직임', content)
        self.assertIn('**AAPL** 실적 발표: 2026-04-14 (D-6)', content)
        self.assertIn('**AAPL** [실적] [Apple Inc., 10-Q 분기 실적 관련 보고서를 SEC에 제출](https://example.com/apple-sec-10q) (2026-04-06)', content)

    def test_render_ticker_markdown_includes_period_quarterly_events_and_timeline(self) -> None:
        content = render_ticker_markdown(
            _sample_analysis(),
            period_changes={'7d': '+3.25%', '30d': '+8.10%'},
            recent_timeline=[
                {
                    'date': '2026-04-08',
                    'signal_or_takeaway': '관찰 지속',
                    'top_news_summary': '애플 관련 핵심 뉴스 요약',
                }
            ],
        )

        self.assertIn('## 최근 변화 비교', content)
        self.assertIn('- 7일 변화: +3.25%', content)
        self.assertIn('- 뉴스 톤: bullish (6.0 / 10)', content)
        self.assertIn('## 최근 4분기 재무', content)
        self.assertIn('| 2025-Q4 | 120.00B USD (+20.0% YoY) | 35.00B USD (+16.7% YoY) | 2.10 USD/share (+16.7% YoY) |', content)
        self.assertIn('## 다가오는 일정', content)
        self.assertIn('실적 발표: 2026-04-14 (D-6)', content)
        self.assertIn('## 최근 타임라인', content)
        self.assertIn('2026-04-08: 관찰 지속 | 애플 관련 핵심 뉴스 요약', content)
        self.assertIn('| 거래량 | 12.30M 주 |', content)
        self.assertIn('| 3개월 평균 거래량 | 18.50M 주 |', content)
        self.assertIn('| EPS (TTM) | 6.10 USD/share |', content)
        self.assertIn('| 52주 최고 | 110.00 USD |', content)
        self.assertNotIn('Apple legacy milestone feature', content)
        self.assertLess(content.find('Apple earnings beat expectations'), content.find('Apple product preview gains attention'))

    def test_append_price_history_replaces_same_day_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / 'price_history.csv'
            append_price_history(csv_path, [_sample_analysis()])
            append_price_history(csv_path, [_sample_analysis()])
            with csv_path.open('r', encoding='utf-8', newline='') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['ticker'], 'AAPL')

    def test_write_json_outputs_writes_dashboard_price_history_and_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output_root = temp_path / 'output'
            data_dir = output_root / 'data'
            web_data_dir = temp_path / 'web' / 'public' / 'output' / 'data'
            data_dir.mkdir(parents=True, exist_ok=True)
            (temp_path / 'web').mkdir(parents=True, exist_ok=True)
            (data_dir / 'price_history.csv').write_text(
                '\n'.join(
                    [
                        'date,ticker,price,daily_change,market_cap,trailing_pe,eps,52w_high,52w_low',
                        '2026-03-31,AAPL,95.00 USD,+0.50%,1.00T,25.00,6.10,110.00,80.00',
                        '2026-04-08,AAPL,100.00 USD,+1.23%,1.00T,25.00,6.10,110.00,80.00',
                    ]
                ),
                encoding='utf-8',
            )

            timelines = write_json_outputs(
                [_sample_analysis()],
                date(2026, 4, 8),
                market_overview=[{'label': 'S&P 500', 'symbol': '^GSPC', 'price': '5,234.18', 'change': '+0.45%'}],
                output_root=output_root,
                period_changes_by_ticker={'AAPL': {'7d': '+3.25%', '30d': 'N/A'}},
                portfolio_summary=PortfolioSummary(
                    positions=[
                        PortfolioPosition(
                            ticker='AAPL',
                            shares=10,
                            avg_cost=90.0,
                            currency='USD',
                            market_price=100.0,
                            market_value=1000.0,
                            cost_basis=900.0,
                            unrealized_pnl=100.0,
                            unrealized_return_pct=11.11,
                        )
                    ],
                    total_market_value=1000.0,
                    total_cost_basis=900.0,
                    total_unrealized_pnl=100.0,
                    total_unrealized_return_pct=11.11,
                ),
            )

            dashboard = json.loads((web_data_dir / 'dashboard.json').read_text(encoding='utf-8'))
            price_history = json.loads((web_data_dir / 'price_history.json').read_text(encoding='utf-8'))
            timeline = json.loads((web_data_dir / 'ticker_timelines.json').read_text(encoding='utf-8'))

            self.assertIn('AAPL', timelines)
            self.assertEqual(dashboard['days'][0]['portfolio_summary']['positions'][0]['ticker'], 'AAPL')
            self.assertEqual(dashboard['days'][0]['tickers'][0]['period_changes']['7d'], '+3.25%')
            self.assertEqual(dashboard['days'][0]['tickers'][0]['news_tone']['label'], 'bullish')
            self.assertEqual(dashboard['days'][0]['tickers'][0]['upcoming_events'][0]['label'], '실적 발표')
            self.assertEqual(dashboard['days'][0]['tickers'][0]['sec_filing_tags'], ['실적'])
            self.assertEqual(dashboard['days'][0]['tickers'][0]['sec_filings'][0]['tag'], '실적')
            self.assertEqual(dashboard['days'][0]['tickers'][0]['sec_filings'][0]['form_type'], '10-Q')
            self.assertEqual(
                dashboard['days'][0]['tickers'][0]['sec_filings'][0]['title'],
                'Apple Inc., 10-Q 분기 실적 관련 보고서를 SEC에 제출',
            )
            self.assertEqual(price_history[-1]['ticker'], 'AAPL')
            self.assertEqual(timeline['AAPL'][0]['top_news_summary'], '애플 실적이 예상치를 웃돌았습니다.')


if __name__ == '__main__':
    unittest.main()
