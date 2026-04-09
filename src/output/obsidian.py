from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path

from src.utils.env import normalize_env_value
from src.utils.pipeline_logging import record_pipeline_event


logger = logging.getLogger(__name__)
_OBSIDIAN_SUBDIR = "pkrich"


def mirror_markdown_outputs(
    daily_path: Path,
    ticker_paths: dict[str, Path],
) -> None:
    vault_path = normalize_env_value(os.getenv("OBSIDIAN_VAULT_PATH"))
    if not vault_path:
        return

    target_root = Path(vault_path).expanduser() / _OBSIDIAN_SUBDIR
    _copy_with_warning(
        daily_path,
        target_root / "daily" / daily_path.name,
        artifact="daily_note",
    )

    for ticker, source_path in ticker_paths.items():
        _copy_with_warning(
            source_path,
            target_root / "tickers" / ticker / source_path.name,
            artifact="ticker_note",
            ticker=ticker,
        )


def _copy_with_warning(
    source_path: Path,
    target_path: Path,
    *,
    artifact: str,
    ticker: str | None = None,
) -> None:
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
    except Exception as exc:
        payload = {
            "artifact": artifact,
            "source_path": str(source_path),
            "target_path": str(target_path),
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
        if ticker:
            payload["ticker"] = ticker
        logger.warning(json.dumps({"event": "obsidian_sync_failed", **payload}, ensure_ascii=True, sort_keys=True))
        record_pipeline_event("output", "warning", "obsidian_sync_failed", **payload)
