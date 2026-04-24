from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.output.pm_view import build_pm_view
from src.types import TickerDecision


def _analysis(
    ticker: str,
    *,
    sector: str,
    upcoming_events: list[dict[str, str]] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        ticker=ticker,
        name=ticker,
        date='2026-04-24',
        summary=f'{ticker} summary',
        data_snapshot={'Sector': sector},
        upcoming_events=upcoming_events or [],
    )


def _portfolio_summary(*tickers: str) -> SimpleNamespace:
    return SimpleNamespace(
        positions=[SimpleNamespace(ticker=ticker) for ticker in tickers],
    )


def _decision(action: str, conviction: int) -> TickerDecision:
    return TickerDecision(
        ticker='',
        action=action,
        conviction=conviction,
        reason=f'{action} decision reason',
        valid_until='2026-04-30',
        factors={},
    )


class PMViewTests(unittest.TestCase):
    def test_build_pm_view_derives_swap_event_and_priority_items(self) -> None:
        analyses = [
            _analysis(
                'NVDA',
                sector='Technology',
                upcoming_events=[
                    {'type': 'earnings', 'label': 'Earnings', 'date': '2026-04-29', 'days_until': '5', 'timing': 'AMC'},
                ],
            ),
            _analysis(
                'AVGO',
                sector='Technology',
            ),
            _analysis(
                'XOM',
                sector='Energy',
            ),
        ]

        pm_view = build_pm_view(
            analyses,
            as_of='2026-04-24',
            portfolio_summary=_portfolio_summary('NVDA'),
            portfolio_risk={
                'risk_grade': 'D',
                'positions_by_weight': [
                    {'ticker': 'NVDA', 'weight': 0.42, 'sector': 'Technology'},
                ],
            },
            decision_map={
                'NVDA': _decision('watch', 58),
                'AVGO': _decision('buy', 82),
                'XOM': _decision('buy', 70),
            },
        )

        self.assertEqual(pm_view['as_of'], '2026-04-24')
        self.assertIn('swap_candidates', pm_view)
        self.assertIn('event_exposure_items', pm_view)
        self.assertIn('today_priority_queue', pm_view)
        self.assertIn('empty_states', pm_view)
        self.assertEqual(pm_view['swap_candidates'][0]['held_ticker'], 'NVDA')
        self.assertEqual(pm_view['swap_candidates'][0]['candidate_ticker'], 'AVGO')
        self.assertEqual(pm_view['swap_candidates'][0]['overlap_context'], 'Same sector: Technology')
        self.assertIn('conviction', ' '.join(pm_view['swap_candidates'][0]['reasons']).lower())
        self.assertEqual(pm_view['event_exposure_items'][0]['ticker'], 'NVDA')
        self.assertEqual(pm_view['event_exposure_items'][0]['event_label'], 'Earnings')
        self.assertEqual(pm_view['today_priority_queue'][0]['today_priority_score'], max(
            item['today_priority_score'] for item in pm_view['today_priority_queue']
        ))
        self.assertGreaterEqual(
            pm_view['today_priority_queue'][0]['today_priority_score'],
            pm_view['today_priority_queue'][-1]['today_priority_score'],
        )

    def test_build_pm_view_returns_explanatory_empty_states_without_portfolio(self) -> None:
        pm_view = build_pm_view(
            [
                _analysis('AVGO', sector='Technology'),
            ],
            as_of='2026-04-24',
            portfolio_summary=None,
            portfolio_risk={},
            decision_map={
                'AVGO': _decision('buy', 82),
            },
        )

        self.assertEqual(pm_view['swap_candidates'], [])
        self.assertEqual(pm_view['event_exposure_items'], [])
        self.assertEqual(pm_view['today_priority_queue'], [])
        self.assertIn('portfolio', pm_view['empty_states']['swap_candidates'].lower())
        self.assertIn('portfolio', pm_view['empty_states']['event_exposure_items'].lower())
        self.assertIn('portfolio', pm_view['empty_states']['today_priority_queue'].lower())

    def test_build_pm_view_is_additive_and_never_changes_official_actions(self) -> None:
        nvda = _analysis('NVDA', sector='Technology')
        avgo = _analysis('AVGO', sector='Technology')
        decision_map = {
            'NVDA': _decision('watch', 58),
            'AVGO': _decision('buy', 82),
        }

        pm_view = build_pm_view(
            [nvda, avgo],
            as_of='2026-04-24',
            portfolio_summary=_portfolio_summary('NVDA'),
            portfolio_risk={},
            decision_map=decision_map,
        )

        self.assertEqual(decision_map['NVDA'].action, 'watch')
        self.assertEqual(decision_map['AVGO'].action, 'buy')
        queue_text = ' '.join(item['summary'] for item in pm_view['today_priority_queue']).lower()
        self.assertNotIn('sell', queue_text)
        self.assertNotIn('rotate now', queue_text)

    def test_build_pm_view_excludes_same_sector_watch_and_avoid_swap_candidates(self) -> None:
        pm_view = build_pm_view(
            [
                _analysis('NVDA', sector='Technology'),
                _analysis('AMD', sector='Technology'),
                _analysis('INTC', sector='Technology'),
            ],
            as_of='2026-04-24',
            portfolio_summary=_portfolio_summary('NVDA'),
            portfolio_risk={},
            decision_map={
                'NVDA': _decision('watch', 58),
                'AMD': _decision('watch', 91),
                'INTC': _decision('avoid', 95),
            },
        )

        self.assertEqual(pm_view['swap_candidates'], [])

    def test_build_pm_view_selects_nearest_upcoming_event_when_events_are_out_of_order(self) -> None:
        pm_view = build_pm_view(
            [
                _analysis(
                    'NVDA',
                    sector='Technology',
                    upcoming_events=[
                        {'type': 'conference', 'label': 'Developer Conference', 'date': '2026-05-10', 'days_until': 'N/A'},
                        {'type': 'earnings', 'label': 'Earnings', 'date': '2026-04-26', 'days_until': '2'},
                        {'type': 'macro', 'label': 'Fed Meeting', 'date': '2026-05-01'},
                    ],
                ),
                _analysis('AVGO', sector='Technology'),
            ],
            as_of='2026-04-24',
            portfolio_summary=_portfolio_summary('NVDA'),
            portfolio_risk={},
            decision_map={
                'NVDA': _decision('watch', 58),
                'AVGO': _decision('buy', 82),
            },
        )

        self.assertEqual(pm_view['event_exposure_items'][0]['event_label'], 'Earnings')
        self.assertEqual(pm_view['event_exposure_items'][0]['days_until'], 2)


if __name__ == '__main__':
    unittest.main()
