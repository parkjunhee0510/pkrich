from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

ValidatorFn = Callable[[dict[str, Any]], bool]


@dataclass(frozen=True)
class PromptContext:
    run_date: date
    macro_context: dict[str, Any] | None = None
    account_size_hint: float | None = None
    model_profile: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    version: str
    system_template: str
    user_template: str
    output_schema: dict[str, Any]
    validator: ValidatorFn | None = None

    def render_system(self, ctx: PromptContext) -> str:
        return self.system_template.format(
            run_date=ctx.run_date.isoformat(),
            prompt_version=self.version,
            **ctx.metadata,
        )

    def render_user(self, ticker_data: dict[str, Any], ctx: PromptContext) -> str:
        render_args = {
            "run_date": ctx.run_date.isoformat(),
            "batch_payload_json": json.dumps(ticker_data, ensure_ascii=True),
            "account_size_hint": ctx.account_size_hint if ctx.account_size_hint is not None else "N/A",
            **ctx.metadata,
        }
        if isinstance(ticker_data, dict):
            render_args.update(ticker_data)
        return self.user_template.format(**render_args)

    def validate_response(self, response: dict[str, Any]) -> bool:
        _validate_against_schema(response, self.output_schema)
        if self.validator is not None:
            return self.validator(response)
        return True


def _validate_against_schema(value: Any, schema: dict[str, Any], *, path: str = "root") -> None:
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(value, dict):
            raise ValueError(f"{path} must be an object")
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise ValueError(f"{path}.{key} is required")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unexpected = set(value) - set(properties)
            if unexpected:
                raise ValueError(f"{path} has unexpected properties: {', '.join(sorted(unexpected))}")
        for key, child_schema in properties.items():
            if key in value:
                _validate_against_schema(value[key], child_schema, path=f"{path}.{key}")
        return

    if schema_type == "array":
        if not isinstance(value, list):
            raise ValueError(f"{path} must be an array")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate_against_schema(item, item_schema, path=f"{path}[{index}]")
        return

    if schema_type == "string":
        if not isinstance(value, str):
            raise ValueError(f"{path} must be a string")
        min_length = schema.get("minLength")
        if min_length is not None and len(value) < int(min_length):
            raise ValueError(f"{path} must be at least {min_length} characters")
        return

    if schema_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{path} must be an integer")
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and value < int(minimum):
            raise ValueError(f"{path} must be >= {minimum}")
        if maximum is not None and value > int(maximum):
            raise ValueError(f"{path} must be <= {maximum}")
        return
