"""Analyzer modules."""

from src.analyzer.modules.legacy_research_note import LegacyResearchNoteModule
from src.analyzer.modules.news_analysis_module import NewsAnalysisModule
from src.analyzer.modules.peer_comparison_module import PeerComparisonModule
from src.analyzer.modules.portfolio_risk_module import PortfolioRiskModule
from src.analyzer.modules.research_narrative_module import ResearchNarrativeModule
from src.analyzer.modules.risk_assessment_module import RiskAssessmentModule
from src.analyzer.modules.signal_takeaway_module import SignalTakeawayModule
from src.analyzer.modules.trade_frame_module import TradeFrameModule
from src.analyzer.modules.valuation_module import ValuationModule
from src.analyzer.modules.weekly_insight_module import WeeklyInsightModule

__all__ = [
    "LegacyResearchNoteModule",
    "NewsAnalysisModule",
    "PeerComparisonModule",
    "PortfolioRiskModule",
    "ResearchNarrativeModule",
    "RiskAssessmentModule",
    "SignalTakeawayModule",
    "TradeFrameModule",
    "ValuationModule",
    "WeeklyInsightModule",
]
