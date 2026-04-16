from __future__ import annotations

from typing import Any

from src.analyzer.base import AnalysisContext, AnalysisModule, ModuleResult
from src.analyzer import research_note


class ValuationModule(AnalysisModule):
    name = "valuation_module"
    requires = {"fundamentals", "price"}
    produces = {"valuation_score"}
    priority = 10
    llm_required = False

    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        results: dict[str, dict[str, Any]] = {}
        for item in ctx.watchlist:
            ticker = item.ticker
            market = ctx.collected[ticker]
            raw_payload = ctx.raw_payload_by_ticker.get(ticker, {})
            score = 5.0
            factors: list[str] = []

            pe_value = research_note._parse_float_from_text(market.pe_ratio)
            target_value = research_note._parse_float_from_text(market.analyst_target_price)
            price = market.price
            roe_value = research_note._parse_float_from_text(market.fundamental_metrics.get("roe")) if isinstance(market.fundamental_metrics, dict) else None
            fcf_yield = research_note._parse_float_from_text(market.fundamental_metrics.get("fcf_yield")) if isinstance(market.fundamental_metrics, dict) else None
            sector_context = ctx.intermediate_results.get(ticker, {}).get("sector_comparison", {})
            if not sector_context:
                sector_context = research_note._format_sector_comparison(raw_payload.get("sector_peer_context", {}))
            sector_pe = research_note._parse_float_from_text(str(sector_context.get("average_pe", "N/A")))

            if pe_value is not None and sector_pe is not None:
                diff_pct = ((pe_value - sector_pe) / sector_pe) * 100 if sector_pe else 0.0
                if diff_pct <= -15:
                    score += 2.5
                    factors.append(f"섹터 평균 PER 대비 {diff_pct:.1f}% 할인")
                elif diff_pct >= 15:
                    score -= 2.5
                    factors.append(f"섹터 평균 PER 대비 {diff_pct:.1f}% 프리미엄")
            elif pe_value is not None:
                factors.append(f"PER {pe_value:.1f}x")

            if price is not None and target_value is not None and target_value > 0:
                upside = ((target_value - price) / price) * 100
                if upside >= 15:
                    score += 1.5
                elif upside <= -10:
                    score -= 1.5
                factors.append(f"목표가 대비 업사이드 {upside:+.1f}%")

            if roe_value is not None:
                if roe_value >= 20:
                    score += 1.5
                elif roe_value <= 8:
                    score -= 1.0
                factors.append(f"ROE {roe_value:.1f}%")

            if fcf_yield is not None:
                if fcf_yield >= 4:
                    score += 1.0
                elif fcf_yield <= 1:
                    score -= 0.5
                factors.append(f"FCF Yield {fcf_yield:.1f}%")

            score = max(1.0, min(10.0, score))
            if score >= 8:
                assessment = "저평가 구간으로 해석할 수 있는 밸류에이션입니다."
            elif score >= 5:
                assessment = "대체로 적정 가치 범위에 위치합니다."
            else:
                assessment = "현재 가격 기준 밸류에이션 부담이 큽니다."

            results[ticker] = {
                "valuation_score": {
                    "score": f"{round(score):.0f}/10",
                    "factors": factors[:4] or ["기초 밸류에이션 데이터 제한"],
                    "assessment": assessment,
                }
            }
        return ModuleResult(results_by_ticker=results)
