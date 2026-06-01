from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.utils.config import load_sectors, load_watchlist


class LoadWatchlistTests(unittest.TestCase):
    def test_load_watchlist_reads_expected_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / 'watchlist.yaml'
            config_path.write_text(
                '\n'.join(
                    [
                        'watchlist:',
                        '  - ticker: AAPL',
                        '    name: Apple Inc.',
                        '    sector: Technology',
                        '    keywords: ["iPhone", "AI"]',
                        '    exclude_keywords: ["rumor", "supply chain check"]',
                        '    cik: "320193"',
                        '    ir_rss_feeds: ["https://www.apple.com/newsroom/rss-feed.rss"]',
                        '    ir_source_names:',
                        '      apple.com: Apple Investor Updates',
                        '    sec_filing_tag_priority:',
                        '      실적: 160',
                    ]
                ),
                encoding='utf-8',
            )

            items = load_watchlist(str(config_path))

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].ticker, 'AAPL')
            self.assertEqual(items[0].name, 'Apple Inc.')
            self.assertEqual(items[0].sector, 'Technology')
            self.assertEqual(items[0].keywords, ['iPhone', 'AI'])
            self.assertEqual(items[0].exclude_keywords, ['rumor', 'supply chain check'])
            self.assertEqual(items[0].cik, '0000320193')
            self.assertEqual(items[0].ir_rss_feeds, ['https://www.apple.com/newsroom/rss-feed.rss'])
            self.assertEqual(items[0].ir_source_names, {'apple.com': 'Apple Investor Updates'})
            self.assertEqual(items[0].sec_filing_tag_priority, {'실적': 160})


class LoadSectorsTests(unittest.TestCase):
    def test_default_sector_explorer_includes_energy_sector(self) -> None:
        sectors = load_sectors()
        energy = next((sector for sector in sectors if sector.id == 'energy'), None)

        self.assertIsNotNone(energy)
        self.assertEqual(energy.name, '에너지')
        self.assertIn('석유', energy.description)
        self.assertEqual(energy.benchmark_etf, 'XLE')
        self.assertIn('oil', energy.news_keywords)

        tickers = {ticker.ticker for ticker in energy.tickers}
        self.assertIn('XOM', tickers)
        self.assertIn('OXY', tickers)

    def test_default_sector_explorer_includes_korean_expansion_sectors(self) -> None:
        sectors = load_sectors()
        by_id = {sector.id: sector for sector in sectors}

        self.assertEqual(by_id['materials'].name, '소재·핵심 광물')
        self.assertEqual(by_id['materials'].benchmark_etf, 'XLB')
        self.assertIn('copper', by_id['materials'].news_keywords)
        self.assertIn('FCX', {ticker.ticker for ticker in by_id['materials'].tickers})
        self.assertIn('DD', {ticker.ticker for ticker in by_id['materials'].tickers})

        self.assertEqual(by_id['cloud_software'].name, '클라우드·기업용 소프트웨어')
        self.assertEqual(by_id['cloud_software'].benchmark_etf, 'IGV')
        self.assertIn(
            'MSFT',
            {ticker.ticker for ticker in by_id['cloud_software'].tickers},
        )

        self.assertEqual(by_id['transport_logistics'].name, '운송·물류')
        self.assertEqual(by_id['transport_logistics'].benchmark_etf, 'IYT')
        self.assertIn(
            'UNP',
            {ticker.ticker for ticker in by_id['transport_logistics'].tickers},
        )

    def test_sector_explorer_includes_new_pipeline_tickers(self) -> None:
        sectors = load_sectors()
        by_id = {sector.id: sector for sector in sectors}

        self.assertIn(
            'DD',
            {ticker.ticker for ticker in by_id['materials'].tickers},
        )
        self.assertIn(
            'XYL',
            {ticker.ticker for ticker in by_id['industrial_infra'].tickers},
        )


if __name__ == '__main__':
    unittest.main()
