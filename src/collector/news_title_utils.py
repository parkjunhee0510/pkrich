from __future__ import annotations

import re

# Broken upstream templates have appeared in multiple capitalizations:
# META_TITLE_QUOTE, Meta_Title_Quote, meta_title_quote, etc.
_PLACEHOLDER_TOKEN_RE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", re.IGNORECASE)


def looks_like_unresolved_placeholder(title: str) -> bool:
    """Return True when a headline still contains a template placeholder."""
    return bool(_PLACEHOLDER_TOKEN_RE.search(title or ""))


__all__ = ["looks_like_unresolved_placeholder"]
