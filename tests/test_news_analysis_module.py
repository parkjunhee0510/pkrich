import unittest

from src.analyzer.modules.news_analysis_module import NewsAnalysisModule


class NewsAnalysisModulePromptTests(unittest.TestCase):
    def test_key_news_prompt_blocks_rewritten_english_headlines(self) -> None:
        prompt = NewsAnalysisModule().build_user_prompt(
            [
                {
                    "ticker": "AAPL",
                    "news": [{"title": "Apple shares rise as AI demand improves"}],
                }
            ],
            None,  # type: ignore[arg-type]
        )

        self.assertIn("입력 뉴스 순서", prompt)
        self.assertIn("의역한 영어 헤드라인을 만들지 마세요", prompt)
        self.assertIn("입력 title과 완전히 동일하게 복사", prompt)


if __name__ == "__main__":
    unittest.main()
