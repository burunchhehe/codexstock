from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .imports import import_from_source
from .registry import get_project


BacktestEngine = Literal["backtrader", "zipline"]


@dataclass
class BacktestLab:
    """Event-driven backtesting facade for backtrader and zipline."""

    engine: BacktestEngine = "backtrader"

    def module(self) -> Any:
        project = get_project(self.engine)
        return import_from_source(self.engine, project.path)

    def cerebro(self) -> Any:
        if self.engine != "backtrader":
            raise ValueError("cerebro() is only available for the backtrader engine")
        return self.module().Cerebro()
