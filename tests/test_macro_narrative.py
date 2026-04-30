from __future__ import annotations

import json
from datetime import date

from src.analyzer.macro_narrative import build_macro_narrative
from src.types import MarketRegime


def test_build_macro_narrative_records_fallback_evidence(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    regime = MarketRegime(regime="neutral", drivers={"vix": "VIX 18 [점수 +1]"})

    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "src.analyzer.macro_narrative.write_evidence_record",
        lambda record, *, run_date: calls.append(record) or True,
    )

    build_macro_narrative({"vix": {"level": "18"}}, regime, date(2026, 4, 30))

    assert len(calls) == 1
    assert calls[0]["scope"] == "run"
    assert calls[0]["module"] == "macro_narrative"
    assert calls[0]["cache_status"] == "fallback"
    assert calls[0]["source"] == "fallback"
    assert str(calls[0]["macro_context_hash"]).startswith("sha256:")


def test_build_macro_narrative_records_cache_hit_evidence(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    cache_path = tmp_path / "output" / "cache" / "macro_narrative_2026-04-30.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "headline": "cached",
                "three_themes": ["theme 1", "theme 2", "theme 3"],
                "risk_map": "risk",
                "what_changed_this_week": "changed",
                "key_headlines": [],
                "source": "llm",
                "model": "gpt-5.4",
            }
        ),
        encoding="utf-8",
    )
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "src.analyzer.macro_narrative.write_evidence_record",
        lambda record, *, run_date: calls.append(record) or True,
    )

    build_macro_narrative({"vix": {"level": "18"}}, MarketRegime(regime="neutral"), date(2026, 4, 30))

    assert len(calls) == 1
    assert calls[0]["cache_status"] == "hit"
    assert calls[0]["source"] == "llm"


def test_build_macro_narrative_ignores_evidence_emit_failures(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "src.analyzer.macro_narrative.evidence_hash",
        lambda _value: (_ for _ in ()).throw(RuntimeError("hash boom")),
    )

    result = build_macro_narrative({"vix": {"level": "18"}}, MarketRegime(regime="neutral"), date(2026, 4, 30))

    assert result["source"] == "fallback"
