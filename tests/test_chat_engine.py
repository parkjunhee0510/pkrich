from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.chat.engine import answer_question


class ChatEngineTests(unittest.TestCase):
    def test_answer_question_uses_fallback_summary_without_openai(self) -> None:
        payload = {
            "days": [
                {
                    "date": "2026-04-10",
                    "tickers": [
                        {
                            "ticker": "AAPL",
                            "name": "Apple",
                            "summary": "애플은 실적 기대가 유지되고 있습니다.",
                            "signal_or_takeaway": "단기 관점에서 강세 유지.",
                            "news_tone": {"label": "bullish"},
                            "key_news": ["iPhone demand steady"],
                            "news_references": [{"title": "Apple news", "link": "https://example.com", "source": "Example", "published_at": "2026-04-10"}],
                        }
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_root = Path(tmp_dir) / "output"
            data_dir = output_root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "index.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "date": "2026-04-10",
                        "market_overview": [],
                        "macro_context": {},
                        "market_regime": {},
                        "portfolio_summary": None,
                        "portfolio_risk": {},
                        "signal_stats": {},
                        "weekly_summary": {},
                        "tickers": payload["days"][0]["tickers"],
                    }
                ),
                encoding="utf-8",
            )

            response = answer_question("AAPL 어때?", output_root=output_root)

        self.assertIn("AAPL", response["answer"])
        self.assertEqual(response["matched_tickers"], ["AAPL"])
        self.assertEqual(len(response["sources"]), 1)

    def test_answer_question_accepts_message_history(self) -> None:
        payload = {
            "days": [
                {
                    "date": "2026-04-10",
                    "tickers": [
                        {
                            "ticker": "AAPL",
                            "name": "Apple",
                            "summary": "애플은 실적 기대가 유지되고 있습니다.",
                            "signal_or_takeaway": "단기 관점에서 강세 유지.",
                            "news_tone": {"label": "bullish"},
                            "key_news": ["iPhone demand steady"],
                            "news_references": [],
                        }
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_root = Path(tmp_dir) / "output"
            data_dir = output_root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "index.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "date": "2026-04-10",
                        "market_overview": [],
                        "macro_context": {},
                        "market_regime": {},
                        "portfolio_summary": None,
                        "portfolio_risk": {},
                        "signal_stats": {},
                        "weekly_summary": {},
                        "tickers": payload["days"][0]["tickers"],
                    }
                ),
                encoding="utf-8",
            )

            response = answer_question(
                "그럼 리스크는?",
                output_root=output_root,
                messages=[
                    {"role": "user", "content": "AAPL 어때?"},
                    {"role": "assistant", "content": "애플은 강세 유지입니다."},
                ],
            )

        self.assertIn("AAPL", response["answer"])
        self.assertEqual(response["matched_tickers"], ["AAPL"])


if __name__ == "__main__":
    unittest.main()
