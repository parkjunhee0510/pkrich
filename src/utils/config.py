from __future__ import annotations

from pathlib import Path

from src.types import WatchlistItem


def load_watchlist(path: str = "config/watchlist.yaml") -> list[WatchlistItem]:
    raw_lines = Path(path).read_text(encoding="utf-8").splitlines()
    items: list[WatchlistItem] = []
    current: dict[str, object] | None = None

    for line in raw_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "watchlist:":
            continue

        if stripped.startswith("- "):
            if current:
                items.append(_build_watchlist_item(current))
            current = {}
            key, value = _split_key_value(stripped[2:])
            current[key] = _parse_value(value)
            continue

        if current is None:
            continue

        key, value = _split_key_value(stripped)
        current[key] = _parse_value(value)

    if current:
        items.append(_build_watchlist_item(current))

    return items


def _split_key_value(line: str) -> tuple[str, str]:
    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def _parse_value(value: str) -> object:
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [part.strip().strip('"').strip("'") for part in inner.split(",")]
    return value.strip('"').strip("'")


def _build_watchlist_item(raw: dict[str, object]) -> WatchlistItem:
    return WatchlistItem(
        ticker=str(raw.get("ticker", "")).upper(),
        name=str(raw.get("name", "")),
        sector=str(raw.get("sector", "")),
        keywords=list(raw.get("keywords", [])),
    )
