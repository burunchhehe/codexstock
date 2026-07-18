from __future__ import annotations

from dataclasses import dataclass, field

from .ai import AILab
from .autotrade import AutoTradeBot
from .backtest import BacktestLab
from .data import MarketData
from .engine import LeanBridge
from .research import ResearchLab


@dataclass
class StockSuite:
    data: MarketData = field(default_factory=MarketData)
    research: ResearchLab = field(default_factory=ResearchLab)
    backtest: BacktestLab = field(default_factory=BacktestLab)
    ai: AILab = field(default_factory=AILab)
    engine: LeanBridge = field(default_factory=LeanBridge)
    autotrade: AutoTradeBot = field(default_factory=AutoTradeBot)
