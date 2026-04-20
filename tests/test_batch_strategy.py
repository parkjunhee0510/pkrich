from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.analyzer.research_note import _PreparedPayloadItem, _build_batches_for_analysis, _calculate_batch_size
from src.types import WatchlistItem
from src.utils.model_config import ModelProfile
from src.utils.token_estimator import estimate_batch_tokens


class BatchStrategyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = ModelProfile(
            name='test',
            model='gpt-5.4-mini',
            context_window=2400,
            max_output_tokens=400,
            monthly_cost_estimate_usd=0.0,
            input_cost_per_1m_tokens=0.0,
            cached_input_cost_per_1m_tokens=0.0,
            output_cost_per_1m_tokens=0.0,
            prompt_version='research_v1',
        )

    def _prepared_items(self, count: int) -> list[_PreparedPayloadItem]:
        prepared: list[_PreparedPayloadItem] = []
        for index in range(count):
            payload = {
                'ticker': f'T{index}',
                'name': f'Company {index}',
                'sector': 'Technology',
                'news': [{'title': 'headline ' + ('x' * 800), 'source': 'Reuters'}],
            }
            prepared.append(
                _PreparedPayloadItem(
                    item=WatchlistItem(ticker=f'T{index}', name=f'Company {index}', sector='Technology'),
                    payload=payload,
                    estimated_tokens=estimate_batch_tokens([payload]),
                )
            )
        return prepared

    def test_calculate_batch_size_respects_token_budget(self) -> None:
        payload_items = [prepared.payload for prepared in self._prepared_items(5)]

        batch_size = _calculate_batch_size(payload_items, self.profile)

        self.assertGreaterEqual(batch_size, 1)
        self.assertLess(batch_size, 5)

    def test_build_batches_for_analysis_splits_payloads_by_estimated_tokens(self) -> None:
        prepared_items = self._prepared_items(6)

        batches = _build_batches_for_analysis(prepared_items, self.profile)

        self.assertGreater(len(batches), 1)
        self.assertEqual(sum(len(batch) for batch in batches), 6)

    def test_batch_size_override_takes_priority(self) -> None:
        payload_items = [prepared.payload for prepared in self._prepared_items(6)]
        prepared_items = self._prepared_items(6)

        with patch.dict(os.environ, {'BATCH_SIZE': '2'}, clear=False):
            self.assertEqual(_calculate_batch_size(payload_items, self.profile), 2)
            batches = _build_batches_for_analysis(prepared_items, self.profile)

        self.assertEqual([len(batch) for batch in batches], [2, 2, 2])


if __name__ == '__main__':
    unittest.main()
