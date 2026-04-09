import os
import unittest
from datetime import date
from unittest.mock import patch

from src.output.slack import _is_valid_webhook_url, send_daily_summary
from src.types import TickerAnalysis


class SlackTests(unittest.TestCase):
    def test_is_valid_webhook_url_accepts_http_and_https(self) -> None:
        self.assertTrue(_is_valid_webhook_url('https://hooks.slack.com/services/a/b/c'))
        self.assertTrue(_is_valid_webhook_url('http://localhost/webhook'))
        self.assertFalse(_is_valid_webhook_url('xoxe.xoxp-token'))
        self.assertFalse(_is_valid_webhook_url(''))

    def test_send_daily_summary_skips_invalid_webhook_without_request(self) -> None:
        analysis = TickerAnalysis(
            ticker='AAPL',
            name='Apple Inc.',
            date='2026-04-08',
            summary='요약',
            key_news=['뉴스'],
            news_references=[],
            financial_highlights=['매출 성장'],
            risks_or_watchpoints=['밸류에이션 점검'],
            signal_or_takeaway='계속 추적',
            data_snapshot={'Price': '100.00 USD', 'Daily Change': '+1.00%'},
        )

        with patch.dict(os.environ, {'SLACK_WEBHOOK_URL': 'xoxe.xoxp-token'}, clear=False):
            with patch('src.output.slack.request.urlopen') as mocked_urlopen:
                send_daily_summary([analysis], date(2026, 4, 8))
                mocked_urlopen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
