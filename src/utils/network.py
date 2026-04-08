from __future__ import annotations

import socket
from functools import lru_cache


@lru_cache(maxsize=None)
def can_open_tcp_connection(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
