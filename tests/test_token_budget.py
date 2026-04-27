import unittest

from src.utils.token_budget import (
    count_tokens, split_into_chunks, TokenBudgetExceeded,
)


class TestTokenBudget(unittest.TestCase):
    def test_count_tokens_returns_positive_int(self):
        n = count_tokens("hello world")
        self.assertIsInstance(n, int)
        self.assertGreater(n, 0)

    def test_split_into_chunks_respects_size(self):
        items = [{"t": f"item {i}"} for i in range(60)]
        chunks = split_into_chunks(items, size=25)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[0]), 25)
        self.assertEqual(len(chunks[2]), 10)

    def test_split_empty_list(self):
        self.assertEqual(split_into_chunks([], size=25), [])

    def test_token_budget_exceeded_raises(self):
        big = "x " * 200_000
        with self.assertRaises(TokenBudgetExceeded):
            count_tokens(big, hard_limit=1000)


if __name__ == "__main__":
    unittest.main()
