from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .registry import get_project


@dataclass
class AutoTradeBot:
    """Path-level bridge for the Freqtrade automated trading bot."""

    @property
    def root(self) -> Path:
        return get_project("freqtrade").path

    @property
    def config_examples(self) -> Path:
        return self.root / "config_examples"

    @property
    def user_data(self) -> Path:
        return self.root / "user_data"

    def is_available(self) -> bool:
        return (self.root / "freqtrade").exists()
