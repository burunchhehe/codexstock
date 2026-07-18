from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .imports import import_from_source
from .registry import get_project


@dataclass
class ResearchLab:
    """Fast research facade backed by vectorbt."""

    def module(self) -> Any:
        project = get_project("vectorbt")
        return import_from_source("vectorbt", project.path)

    def portfolio_from_signals(self, *args: Any, **kwargs: Any) -> Any:
        vbt = self.module()
        return vbt.Portfolio.from_signals(*args, **kwargs)
