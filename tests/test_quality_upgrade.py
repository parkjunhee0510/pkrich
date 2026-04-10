from __future__ import annotations

import unittest

from src.pipeline import _score_conviction
from src.types import CollectedTickerData
from src.utils.model_config import load_model_profile


class QualityUpgradeTests(unittest.TestCase):
    def test_score_conviction_uses_three_quality_signals(self) -> None:
        data = CollectedTickerData(
            ticker='AAPL',
            name='Apple Inc.',
            sector='Technology',
            price=100.0,
            change_percent=1.0,
            currency='USD',
            market_cap='1.00T',
            pe_ratio='25.0',
            summary_note='memo',
            options_flow={'flow_sentiment': 'bullish', 'unusual_activity': 'CALL vol=8500'},
            insider_transactions=[{'type': 'buy'}],
            analyst_estimate_revisions={'direction': 'up'},
        )

        self.assertEqual(_score_conviction(data), 3)

    def test_load_model_profile_can_override_profile_name(self) -> None:
        profile = load_model_profile(profile_name='deep')

        self.assertEqual(profile.name, 'deep')
        self.assertEqual(profile.model, 'o3-mini')


if __name__ == '__main__':
    unittest.main()
