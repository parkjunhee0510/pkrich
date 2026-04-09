from __future__ import annotations

import json
from typing import Any

_SYSTEM_PROMPT_TOKENS = 180
_USER_PROMPT_TOKENS = 120
_SCHEMA_TOKENS = 140
_RESPONSE_BUFFER_TOKENS = 80


def estimate_batch_tokens(payload_items: list[dict[str, Any]] | dict[str, Any]) -> int:
    serialized = json.dumps(payload_items, ensure_ascii=True, separators=(',', ':'))
    payload_tokens = max(1, len(serialized) // 4)
    return payload_tokens + _SYSTEM_PROMPT_TOKENS + _USER_PROMPT_TOKENS + _SCHEMA_TOKENS + _RESPONSE_BUFFER_TOKENS
