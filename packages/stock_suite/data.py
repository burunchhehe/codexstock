from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .imports import import_from_source
from .registry import get_project


@dataclass
class MarketData:
    """Market data facade backed by yfinance."""

    def module(self) -> Any:
        project = get_project("yfinance")
        return import_from_source("yfinance", project.path)

    def download(self, *args: Any, **kwargs: Any) -> Any:
        return self.module().download(*args, **kwargs)

    def ticker(self, symbol: str) -> Any:
        return self.module().Ticker(symbol)
