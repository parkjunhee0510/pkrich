from __future__ import annotations

from src.analyzer.prompts.base import PromptTemplate
from src.analyzer.prompts.research_v1 import PROMPT_SET as RESEARCH_V1
from src.analyzer.prompts.research_v2 import PROMPT_SET as RESEARCH_V2

_PROMPT_VERSIONS: dict[str, dict[str, PromptTemplate]] = {
    "research_v1": RESEARCH_V1,
    "research_v2": RESEARCH_V2,
}


def get_prompt_template(prompt_version: str | None, module_name: str) -> PromptTemplate:
    version = prompt_version or "research_v1"
    prompt_set = _PROMPT_VERSIONS.get(version)
    if prompt_set is None:
        raise ValueError(f"Unknown prompt version: {version}")
    if module_name not in prompt_set:
        raise ValueError(f"Prompt version {version} does not define module {module_name}")
    return prompt_set[module_name]
