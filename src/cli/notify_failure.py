from __future__ import annotations

import os
from datetime import date

from src.output.slack import send_pipeline_failure_alert


def main() -> int:
    error_message = os.getenv("PIPELINE_FAILURE_MESSAGE", "").strip() or "GitHub Actions workflow failed"
    send_pipeline_failure_alert(date.today(), error_message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
