from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.utils.config import load_watchlist


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


if __name__ == '__main__':
    unittest.main()
