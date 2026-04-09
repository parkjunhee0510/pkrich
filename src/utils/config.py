from __future__ import annotations

from pathlib import Path
from typing import Any

from src.types import PortfolioHolding, WatchlistItem


def load_watchlist(path: str = 'config/watchlist.yaml') -> list[WatchlistItem]:
    config_path = Path(path)
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(config_path.read_text(encoding='utf-8'))
        watchlist_entries = loaded.get('watchlist', []) if isinstance(loaded, dict) else []
        if isinstance(watchlist_entries, list):
            return [_build_watchlist_item(entry) for entry in watchlist_entries if isinstance(entry, dict)]
    except Exception:
        pass

    raw_lines = config_path.read_text(encoding='utf-8').splitlines()
    items: list[WatchlistItem] = []
    current: dict[str, object] | None = None

    for line in raw_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or stripped == 'watchlist:':
            continue

        if stripped.startswith('- '):
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
    loaded = load_yaml_mapping(path)
    return loaded if isinstance(loaded, dict) else {}


def load_yaml_mapping(path: str, *, optional: bool = False) -> dict[str, Any]:
    config_path = Path(path)
    if optional and not config_path.exists():
        return {}
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(config_path.read_text(encoding='utf-8'))
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        if optional:
            return {}
        raw_lines = config_path.read_text(encoding='utf-8').splitlines()
        result: dict[str, object] = {}
        current_section: str | None = None
        current_mapping: dict[str, object] = {}

        for line in raw_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            if not line.startswith(' ') and stripped.endswith(':'):
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


def load_portfolio(path: str = 'config/portfolio.yaml') -> list[PortfolioHolding]:
    payload = load_yaml_mapping(path, optional=True)
    holdings = payload.get('holdings', [])
    if not isinstance(holdings, list):
        return []

    normalized: list[PortfolioHolding] = []
    for entry in holdings:
        if not isinstance(entry, dict):
            continue
        ticker = str(entry.get('ticker', '')).strip().upper()
        if not ticker:
            continue
        try:
            shares = float(entry.get('shares', 0))
            avg_cost = float(entry.get('avg_cost', 0))
        except (TypeError, ValueError):
            continue
        normalized.append(
            PortfolioHolding(
                ticker=ticker,
                shares=shares,
                avg_cost=avg_cost,
                currency=str(entry.get('currency', 'USD') or 'USD'),
            )
        )
    return normalized


def _split_key_value(line: str) -> tuple[str, str]:
    key, value = line.split(':', 1)
    return key.strip(), value.strip()


def _parse_value(value: str) -> object:
    if value.startswith('[') and value.endswith(']'):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [part.strip().strip('"').strip("'") for part in inner.split(',')]
    return _parse_scalar(value)


def _parse_scalar(value: str) -> object:
    normalized = value.strip('"').strip("'")
    if normalized.lower() in {'true', 'false'}:
        return normalized.lower() == 'true'
    if normalized.lstrip('-').isdigit():
        return int(normalized)
    try:
        return float(normalized)
    except ValueError:
        return normalized


def _build_watchlist_item(raw: dict[str, object]) -> WatchlistItem:
    return WatchlistItem(
        ticker=str(raw.get('ticker', '')).upper(),
        name=str(raw.get('name', '')),
        sector=str(raw.get('sector', '')),
        keywords=list(raw.get('keywords', [])),
        exclude_keywords=list(raw.get('exclude_keywords', [])),
        cik=_normalize_cik(raw.get('cik', '')),
        ir_rss_feeds=_normalize_string_list(raw.get('ir_rss_feeds', [])),
        ir_source_names=_normalize_string_mapping(raw.get('ir_source_names', {})),
        sec_filing_tag_priority=_normalize_int_mapping(raw.get('sec_filing_tag_priority', {})),
    )


def _normalize_cik(value: object) -> str:
    normalized = ''.join(character for character in str(value or '').strip() if character.isdigit())
    if not normalized:
        return ''
    return normalized.zfill(10)


def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def _normalize_string_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, item in value.items():
        normalized_key = str(key).strip().lower()
        normalized_value = str(item).strip()
        if normalized_key and normalized_value:
            normalized[normalized_key] = normalized_value
    return normalized


def _normalize_int_mapping(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, int] = {}
    for key, item in value.items():
        normalized_key = str(key).strip()
        if not normalized_key:
            continue
        try:
            normalized[normalized_key] = int(item)
        except (TypeError, ValueError):
            continue
    return normalized
