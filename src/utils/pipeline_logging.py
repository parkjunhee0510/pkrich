from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any


_MAX_LATEST_ERRORS = 10
_SENSITIVE_FIELD_NAMES = {
    'api_key',
    'apikey',
    'openai_api_key',
    'slack_webhook_url',
    'webhook_url',
    'raw_response',
    'response_body',
    'content',
}
_ACTIVE_LOGGER: 'PipelineRunLogger | None' = None


@dataclass
class PipelineRunLogger:
    run_date: date
    logs_root: Path = field(default_factory=lambda: Path('logs') / 'pipeline')
    latest_errors_limit: int = _MAX_LATEST_ERRORS

    def __post_init__(self) -> None:
        self.logs_root.mkdir(parents=True, exist_ok=True)
        run_key = self.run_date.isoformat()
        self.jsonl_path = self.logs_root / f'{run_key}.jsonl'
        self.summary_path = self.logs_root / f'{run_key}.summary.json'
        self.jsonl_path.write_text('', encoding='utf-8')
        self.component_counts: dict[str, dict[str, int]] = defaultdict(lambda: {'warning': 0, 'error': 0})
        self.ticker_fallbacks: dict[str, bool] = {}
        self.source_failures: dict[str, int] = defaultdict(int)
        self.data_provider_usage: dict[str, int] = defaultdict(int)
        self.latest_errors: deque[dict[str, Any]] = deque(maxlen=self.latest_errors_limit)
        self.top_scored_headlines: dict[str, str] = {}
        self.daily_api_cost_usd = 0.0
        self.llm_usage: dict[str, int] = defaultdict(int)
        self.models_used: dict[str, int] = defaultdict(int)
        self.analyzer_quality: dict[str, int] = defaultdict(int)

    def record(self, component: str, level: str, event: str, **fields: Any) -> None:
        safe_fields = _sanitize_fields(fields)
        payload = {
            'timestamp': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
            'run_date': self.run_date.isoformat(),
            'component': component,
            'level': level,
            'event': event,
            **safe_fields,
        }
        with self.jsonl_path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
            handle.write('\n')

        if level in {'warning', 'error'}:
            self.component_counts[component][level] += 1

        ticker = str(safe_fields.get('ticker', '')).strip()
        if 'fallback' in event and ticker:
            self.ticker_fallbacks[ticker] = True
            self.analyzer_quality['full_fallback_count'] += 1

        source = str(safe_fields.get('source') or safe_fields.get('provider') or '').strip()
        if level in {'warning', 'error'} and source:
            self.source_failures[source] += 1
        if event == 'data_provider_used' and source:
            self.data_provider_usage[source] += 1

        headline_title = str(safe_fields.get('top_scored_headline_title', '')).strip()
        if ticker and headline_title:
            self.top_scored_headlines[ticker] = headline_title

        if event == 'openai_usage_recorded':
            self.daily_api_cost_usd += _coerce_float(safe_fields.get('estimated_cost_usd'))
            for key in ('input_tokens', 'output_tokens', 'cached_input_tokens', 'total_tokens'):
                self.llm_usage[key] += _coerce_int(safe_fields.get(key))
            model = str(safe_fields.get('model', '')).strip()
            if model:
                self.models_used[model] += 1
        elif event == 'analysis_batch_planned':
            self.analyzer_quality['batch_count'] += 1
        elif event == 'openai_response_validation_failed':
            self.analyzer_quality['validation_failure_count'] += 1
        elif event == 'analysis_batch_split_retry':
            self.analyzer_quality['batch_split_retry_count'] += 1

        if level in {'warning', 'error'}:
            self.latest_errors.append(
                {
                    key: value
                    for key, value in payload.items()
                    if key in {
                        'timestamp',
                        'component',
                        'level',
                        'event',
                        'ticker',
                        'source',
                        'provider',
                        'error_type',
                        'error_message',
                        'artifact',
                        'batch_number',
                    }
                }
            )

    def finalize(self, success: bool) -> Path:
        summary = {
            'run_date': self.run_date.isoformat(),
            'success': success,
            'log_path': str(self.jsonl_path),
            'summary_path': str(self.summary_path),
            'component_counts': dict(sorted(self.component_counts.items())),
            'ticker_fallbacks': dict(sorted(self.ticker_fallbacks.items())),
            'source_failures': dict(sorted(self.source_failures.items())),
            'data_provider_usage': dict(sorted(self.data_provider_usage.items())),
            'daily_api_cost_usd': round(self.daily_api_cost_usd, 8),
            'llm_usage': dict(sorted(self.llm_usage.items())),
            'models_used': dict(sorted(self.models_used.items())),
            'analyzer_quality': dict(sorted(self.analyzer_quality.items())),
            'latest_errors': list(self.latest_errors),
            'top_scored_headlines': dict(sorted(self.top_scored_headlines.items())),
        }
        self.summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        return self.summary_path


def start_pipeline_logging(run_date: date, logs_root: Path | None = None) -> PipelineRunLogger:
    global _ACTIVE_LOGGER
    _ACTIVE_LOGGER = PipelineRunLogger(run_date=run_date, logs_root=logs_root or (Path('logs') / 'pipeline'))
    return _ACTIVE_LOGGER


def get_pipeline_logger() -> PipelineRunLogger | None:
    return _ACTIVE_LOGGER


def record_pipeline_event(component: str, level: str, event: str, **fields: Any) -> None:
    logger = get_pipeline_logger()
    if logger is None:
        return
    logger.record(component=component, level=level, event=event, **fields)


def finalize_pipeline_logging(success: bool) -> Path | None:
    global _ACTIVE_LOGGER
    if _ACTIVE_LOGGER is None:
        return None
    summary_path = _ACTIVE_LOGGER.finalize(success=success)
    _ACTIVE_LOGGER = None
    return summary_path


def _sanitize_fields(fields: dict[str, Any]) -> dict[str, Any]:
    safe_fields: dict[str, Any] = {}
    for key, value in fields.items():
        normalized_key = key.strip().lower()
        if normalized_key in _SENSITIVE_FIELD_NAMES:
            continue
        if any(token in normalized_key for token in ('secret', 'token', 'password', 'webhook')):
            continue
        safe_fields[key] = value
    return safe_fields


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
