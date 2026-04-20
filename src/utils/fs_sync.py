"""Resilient filesystem sync helpers.

OneDrive / antivirus processes occasionally hold a brief sync lock on files in
`output/data/` when the pipeline writes several files back-to-back. This
surfaces as transient OSError (Errno 13 / 22 / 32). The helpers in this module
retry with a short backoff so a transient lock does not kill the run.
"""
from __future__ import annotations

import time
from typing import Callable

# Small backoff schedule (seconds). Total worst-case wait ≈ 1.1s.
_RETRY_DELAYS = (0.1, 0.3, 0.7)


def retry_io(op: Callable[[], None], *, what: str) -> None:
    """Retry a filesystem op on transient OSError.

    Args:
        op: Zero-arg callable performing the filesystem operation.
        what: Human-readable description used in the final error message.

    Raises:
        OSError: If every retry still fails. The original error is chained.
    """
    last_err: OSError | None = None
    for delay in (0.0, *_RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        try:
            op()
            return
        except OSError as err:
            last_err = err
    assert last_err is not None
    raise OSError(f"{what} failed after {len(_RETRY_DELAYS)} retries: {last_err}") from last_err
