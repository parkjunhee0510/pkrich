from __future__ import annotations

import tiktoken


_ENC = tiktoken.get_encoding("o200k_base")


class TokenBudgetExceeded(Exception):
    """Raised when input token count exceeds a configured hard limit."""


def count_tokens(text: str, hard_limit: int | None = None) -> int:
    n = len(_ENC.encode(text))
    if hard_limit is not None and n > hard_limit:
        raise TokenBudgetExceeded(f"{n} tokens > hard_limit {hard_limit}")
    return n


def split_into_chunks(items: list, size: int = 25) -> list[list]:
    if size <= 0:
        raise ValueError("chunk size must be positive")
    return [items[i : i + size] for i in range(0, len(items), size)]
