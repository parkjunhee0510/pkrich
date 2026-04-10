from __future__ import annotations

from pathlib import Path
from typing import Any

from src.types import PortfolioHolding, WatchlistItem


def load_watchlist(path: str = 'config/watchlist.yaml') -> list[WatchlistItem]:
    payload = load_yaml_mapping(path)
    watchlist_entries = payload.get('watchlist', [])
    if not isinstance(watchlist_entries, list):
        return []
    return [_build_watchlist_item(entry) for entry in watchlist_entries if isinstance(entry, dict)]


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
        try:
            loaded = _load_yaml_fallback(config_path.read_text(encoding='utf-8'))
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}


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


def _load_yaml_fallback(text: str) -> object:
    lines = _tokenize_yaml_lines(text)
    if not lines:
        return {}
    parsed, _ = _parse_yaml_block(lines, 0, lines[0][0])
    return parsed


def _tokenize_yaml_lines(text: str) -> list[tuple[int, str]]:
    tokens: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(' '))
        tokens.append((indent, stripped))
    return tokens


def _parse_yaml_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[object, int]:
    if index >= len(lines):
        return {}, index
    _, content = lines[index]
    if content.startswith('- '):
        return _parse_yaml_list(lines, index, indent)
    return _parse_yaml_dict(lines, index, indent)


def _parse_yaml_dict(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[dict[str, object], int]:
    result: dict[str, object] = {}
    while index < len(lines):
        line_indent, content = lines[index]
        if line_indent < indent or line_indent != indent or content.startswith('- '):
            break
        key, value = _split_key_value(content)
        index += 1
        if value:
            result[key] = _parse_value(value)
            continue
        if index < len(lines) and lines[index][0] > line_indent:
            nested, index = _parse_yaml_block(lines, index, lines[index][0])
            result[key] = nested
        else:
            result[key] = {}
    return result, index


def _parse_yaml_list(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[list[object], int]:
    result: list[object] = []
    while index < len(lines):
        line_indent, content = lines[index]
        if line_indent < indent or line_indent != indent or not content.startswith('- '):
            break
        item_content = content[2:].strip()
        index += 1

        if not item_content:
            if index < len(lines) and lines[index][0] > line_indent:
                nested, index = _parse_yaml_block(lines, index, lines[index][0])
                result.append(nested)
            else:
                result.append({})
            continue

        if ':' in item_content:
            key, value = _split_key_value(item_content)
            item: dict[str, object] = {}
            if value:
                item[key] = _parse_value(value)
            elif index < len(lines) and lines[index][0] > line_indent:
                nested, index = _parse_yaml_block(lines, index, lines[index][0])
                item[key] = nested
            else:
                item[key] = {}

            while index < len(lines) and lines[index][0] > line_indent:
                child_indent = lines[index][0]
                nested, index = _parse_yaml_block(lines, index, child_indent)
                if isinstance(nested, dict):
                    item.update(nested)
                else:
                    item.setdefault('_items', nested)
            result.append(item)
            continue

        result.append(_parse_value(item_content))
    return result, index


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
