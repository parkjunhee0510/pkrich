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


def load_simple_mapping(path: str) -> dict[str, object]:
    raw_lines = Path(path).read_text(encoding="utf-8").splitlines()
    result: dict[str, object] = {}
    current_section: str | None = None
    current_mapping: dict[str, object] = {}

    for line in raw_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if not line.startswith(" ") and stripped.endswith(":"):
            if current_section is not None:
                result[current_section] = current_mapping
            current_section = stripped[:-1]
            current_mapping = {}
            continue

        if current_section is None:
            key, value = _split_key_value(stripped)
            result[key] = _parse_scalar(value)
            continue

        key, value = _split_key_value(stripped)
        current_mapping[key] = _parse_scalar(value)

    if current_section is not None:
        result[current_section] = current_mapping

    return result


def _split_key_value(line: str) -> tuple[str, str]:
    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def _parse_value(value: str) -> object:
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [part.strip().strip('"').strip("'") for part in inner.split(",")]
    return _parse_scalar(value)


def _parse_scalar(value: str) -> object:
    normalized = value.strip('"').strip("'")
    if normalized.lstrip("-").isdigit():
        return int(normalized)
    return normalized


def _build_watchlist_item(raw: dict[str, object]) -> WatchlistItem:
    return WatchlistItem(
        ticker=str(raw.get("ticker", "")).upper(),
        name=str(raw.get("name", "")),
        sector=str(raw.get("sector", "")),
        keywords=list(raw.get("keywords", [])),
    )
